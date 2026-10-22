import asyncio
import json
import logging
import secrets
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    assert_household_access,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    get_authenticated_identity,
    get_current_user,
)
from app.db.base import Base
from app.db.session import SessionLocal, engine, get_db
from app.models import (
    AnalysisRecord,
    CoachMetric,
    CoachSession,
    DeviceAuthSession,
    Feedback,
    Household,
    Profile,
    SportsEvent,
    ViewingSession,
)
from app.schemas.api import (
    AICommandRequest,
    CoachMetricCreate,
    CoachSessionCreate,
    DemoAuthResponse,
    DeviceAuthorizeRequest,
    DeviceCodeRequest,
    DeviceCodeResponse,
    DeviceTokenRequest,
    ExperienceResolveRequest,
    FeedbackCreate,
    ProfilePreferencesUpdate,
    RefreshTokenRequest,
    SessionCreate,
    TokenResponse,
)
from app.services.ai import analyze_command
from app.services.bootstrap import seed_sample_data, sync_live_sports_events

settings = get_settings()
logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO), format="%(message)s")
logger = logging.getLogger("omnipulse")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_for_startup()
    if settings.environment.lower() != "production":
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            seed_sample_data(db)
            if settings.sports_provider.lower() in ("api-football", "apifootball") and settings.sports_provider_api_key:
                sync_live_sports_events(db)
    yield


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "Idempotency-Key"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", f"req_{uuid4().hex[:16]}")[:100]
    request.state.request_id = request_id
    started = time.perf_counter()
    if request.method in {"POST", "PATCH", "PUT"}:
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > settings.max_request_bytes:
            return JSONResponse(
                status_code=413,
                content={"error": {"code": "REQUEST_TOO_LARGE", "message": "Request body is too large", "request_id": request_id, "retryable": False}},
                headers={"X-Request-ID": request_id, "X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"},
            )
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/v1/") else "no-cache"
    if settings.environment.lower() == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    logger.info(json.dumps({"event": "http_request", "request_id": request_id, "method": request.method, "path": request.url.path, "status": response.status_code, "duration_ms": round((time.perf_counter() - started) * 1000, 2)}, separators=(",", ":")))
    return response


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", request.headers.get("X-Request-ID", ""))
    return JSONResponse(status_code=422, content={"error": {"code": "VALIDATION_ERROR", "message": "Request validation failed. Check the documented request schema.", "request_id": request_id or None, "retryable": False}})


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", request.headers.get("X-Request-ID", ""))
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
    code = {400: "BAD_REQUEST", 401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND", 409: "CONFLICT", 413: "REQUEST_TOO_LARGE", 422: "VALIDATION_ERROR", 429: "RATE_LIMITED"}.get(exc.status_code, "REQUEST_FAILED")
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": code, "message": detail, "request_id": request_id or None, "retryable": exc.status_code in (429, 500, 502, 503, 504)}}, headers=exc.headers)


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", request.headers.get("X-Request-ID", ""))
    logger.error("unhandled_request_error request_id=%s type=%s", request_id, type(exc).__name__, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": "An unexpected server error occurred", "request_id": request_id or None, "retryable": False}},
    )


def _profile_for_user(db: Session, user: dict) -> Profile:
    profile = db.get(Profile, user["profile_id"])
    if not profile or profile.household_id != user["household_id"]:
        raise HTTPException(status_code=403, detail="Profile is not available")
    return profile


def _event_payload(event: SportsEvent) -> dict:
    return {
        "id": event.id, "sport": event.sport, "league": event.league, "title": event.title,
        "home_team": event.home_team, "away_team": event.away_team, "status": event.status,
        "source_type": event.source_type, "score_home": event.score_home, "score_away": event.score_away,
        "starts_at": event.starts_at.isoformat() if event.starts_at else None,
        "updated_at": event.updated_at.isoformat() if event.updated_at else None,
    }


@app.get("/health/live", tags=["health"])
def health_live():
    return {"status": "alive", "service": "omnipulse-api", "version": settings.app_version}


@app.get("/health/ready", tags=["health"])
def health_ready(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        event_count = db.scalar(select(SportsEvent.id).limit(1))
        return {"status": "ready", "database": "ok", "sample_or_provider_data_available": event_count is not None}
    except Exception as exc:
        logger.exception("readiness check failed")
        raise HTTPException(status_code=503, detail="A required dependency is unavailable") from exc


@app.post("/v1/auth/demo", response_model=DemoAuthResponse, tags=["auth"])
def demo_auth(db: Session = Depends(get_db)):
    if not settings.demo_mode or settings.environment.lower() == "production":
        raise HTTPException(status_code=404, detail="Not found")
    subject = "local-demo-user"
    household = db.scalar(select(Household).where(Household.owner_sub == subject))
    if not household:
        household = Household(id="demo-household", name="OmniPulse Demo Household", owner_sub=subject, preferences={"spoiler_policy": "avoid", "default_mode": "analyst"})
        db.add(household)
        db.flush()
        profile = Profile(id="demo-profile", household_id=household.id, nickname="Viewer", profile_type="personal", preferences={"favorite_sports": ["football"], "detail_level": "advanced", "spoiler_policy": "avoid", "default_mode": "analyst"})
        db.add(profile)
        db.commit()
    profile = db.scalar(select(Profile).where(Profile.household_id == household.id).order_by(Profile.created_at).limit(1))
    if not profile:
        profile = Profile(household_id=household.id, nickname="Viewer", preferences={})
        db.add(profile)
        db.commit()
        db.refresh(profile)
    token = create_access_token(subject=subject, household_id=household.id, profile_id=profile.id, demo=True)
    return DemoAuthResponse(access_token=token, expires_in_seconds=settings.jwt_ttl_minutes * 60, household_id=household.id, profile_id=profile.id)


@app.post("/v1/onboarding", tags=["auth"])
def onboarding(identity: dict = Depends(get_authenticated_identity), db: Session = Depends(get_db)):
    """Create the first household/profile for an authenticated Cognito identity."""
    if identity["demo"]:
        raise HTTPException(status_code=409, detail="Demo identities are already provisioned")
    subject = identity["sub"]
    household = db.scalar(select(Household).where(Household.owner_sub == subject))
    if household:
        profile = db.scalar(select(Profile).where(Profile.household_id == household.id).order_by(Profile.created_at).limit(1))
        return {"household_id": household.id, "profile_id": profile.id if profile else None, "created": False}
    household = Household(name="My Household", owner_sub=subject, preferences={"default_mode": "family", "spoiler_policy": "avoid"})
    db.add(household)
    try:
        db.flush()
        profile = Profile(household_id=household.id, nickname="Viewer", profile_type="personal", preferences={"favorite_sports": [], "detail_level": "balanced", "spoiler_policy": "avoid", "default_mode": "family"})
        db.add(profile)
        db.commit()
        db.refresh(household)
        db.refresh(profile)
        return {"household_id": household.id, "profile_id": profile.id, "created": True}
    except Exception as exc:
        from sqlalchemy.exc import IntegrityError
        db.rollback()
        if isinstance(exc, IntegrityError):
            existing = db.scalar(select(Household).where(Household.owner_sub == subject))
            if existing:
                existing_profile = db.scalar(select(Profile).where(Profile.household_id == existing.id).order_by(Profile.created_at).limit(1))
                if existing_profile:
                    return {"household_id": existing.id, "profile_id": existing_profile.id, "created": False}
        raise


@app.post("/v1/auth/device/code", response_model=DeviceCodeResponse, tags=["auth"])
def request_device_code(payload: DeviceCodeRequest = DeviceCodeRequest(), db: Session = Depends(get_db)):
    """Request a device code and user code for TV activation (RFC 8628)."""
    device_code = secrets.token_urlsafe(32)
    part1 = secrets.token_hex(2).upper()
    part2 = secrets.token_hex(2).upper()
    user_code = f"{part1}-{part2}"
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=10)

    session = DeviceAuthSession(
        device_code=device_code,
        user_code=user_code,
        client_id=payload.client_id or "omnipulse-tv-client",
        status="pending",
        interval=5,
        expires_at=expires_at,
        created_at=now,
    )
    db.add(session)
    db.commit()

    return DeviceCodeResponse(
        device_code=device_code,
        user_code=user_code,
        verification_uri="/activate",
        verification_uri_complete=f"/activate?code={user_code}",
        expires_in=600,
        interval=5,
    )


@app.post("/v1/auth/device/token", response_model=TokenResponse, tags=["auth"])
def poll_device_token(payload: DeviceTokenRequest, db: Session = Depends(get_db)):
    """Poll for access token after user authorizes on mobile/browser."""
    session = db.scalar(select(DeviceAuthSession).where(DeviceAuthSession.device_code == payload.device_code))
    if not session:
        raise HTTPException(status_code=400, detail="invalid_grant")

    now = datetime.now(timezone.utc)
    expires = session.expires_at if session.expires_at.tzinfo else session.expires_at.replace(tzinfo=timezone.utc)
    if now > expires:
        session.status = "expired"
        db.commit()
        raise HTTPException(status_code=400, detail="expired_token")

    if session.status == "pending":
        raise HTTPException(status_code=400, detail="authorization_pending")
    elif session.status == "denied":
        raise HTTPException(status_code=400, detail="access_denied")
    elif session.status == "authorized":
        if not session.household_id or not session.profile_id or not session.subject:
            raise HTTPException(status_code=500, detail="Incomplete authorization session")

        access_token = create_access_token(
            subject=session.subject,
            household_id=session.household_id,
            profile_id=session.profile_id,
            demo=False,
        )
        refresh_token = create_refresh_token(
            subject=session.subject,
            household_id=session.household_id,
            profile_id=session.profile_id,
            demo=False,
        )
        session.status = "completed"
        db.commit()
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in_seconds=settings.jwt_ttl_minutes * 60,
            household_id=session.household_id,
            profile_id=session.profile_id,
        )
    else:
        raise HTTPException(status_code=400, detail="invalid_grant")


@app.post("/v1/auth/device/authorize", tags=["auth"])
def authorize_device_session(
    payload: DeviceAuthorizeRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Authorize a pending TV device session using the 6-character user_code."""
    cleaned_code = payload.user_code.strip().upper()
    session = db.scalar(select(DeviceAuthSession).where(
        DeviceAuthSession.user_code == cleaned_code,
        DeviceAuthSession.status == "pending",
    ))
    if not session:
        raise HTTPException(status_code=404, detail="Invalid or expired activation code")

    now = datetime.now(timezone.utc)
    expires = session.expires_at if session.expires_at.tzinfo else session.expires_at.replace(tzinfo=timezone.utc)
    if now > expires:
        session.status = "expired"
        db.commit()
        raise HTTPException(status_code=400, detail="Activation code has expired")

    session.status = "authorized"
    session.subject = user["sub"]
    session.household_id = user["household_id"]
    session.profile_id = user["profile_id"]
    db.commit()
    return {"authorized": True, "user_code": cleaned_code, "household_id": user["household_id"]}


@app.post("/v1/auth/refresh", response_model=TokenResponse, tags=["auth"])
def refresh_session_token(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Exchange a valid refresh token for a fresh access token."""
    claims = decode_refresh_token(payload.refresh_token)
    subject = claims["sub"]
    household_id = claims["household_id"]
    profile_id = claims["profile_id"]

    household = db.get(Household, household_id)
    profile = db.get(Profile, profile_id)
    if not household or not profile or household.owner_sub != subject:
        raise HTTPException(status_code=401, detail="Session is no longer valid")

    access_token = create_access_token(
        subject=subject,
        household_id=household.id,
        profile_id=profile.id,
        demo=bool(claims.get("demo", False)),
    )
    new_refresh_token = create_refresh_token(
        subject=subject,
        household_id=household.id,
        profile_id=profile.id,
        demo=bool(claims.get("demo", False)),
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in_seconds=settings.jwt_ttl_minutes * 60,
        household_id=household.id,
        profile_id=profile.id,
    )


@app.get("/v1/me", tags=["auth"])
def me(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = _profile_for_user(db, user)
    household = db.get(Household, user["household_id"])
    return {"subject": user["sub"], "demo": user["demo"], "household": {"id": household.id, "name": household.name}, "profile": {"id": profile.id, "nickname": profile.nickname, "profile_type": profile.profile_type, "preferences": profile.preferences}}


@app.post("/v1/sports/sync", tags=["sports"])
def sync_sports_data(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Triggers an on-demand sync of live/today matches from configured sports provider."""
    synced = sync_live_sports_events(db)
    return {"status": "ok", "synced_events": synced, "provider": settings.sports_provider}


@app.get("/v1/sports/events", tags=["sports"])
def list_events(sport: str | None = None, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    query = select(SportsEvent).order_by(SportsEvent.title)
    if sport:
        query = query.where(SportsEvent.sport == sport.lower())
    items = [_event_payload(event) for event in db.scalars(query).all()]
    return {"items": items, "count": len(items)}


@app.get("/v1/sports/events/{event_id}", tags=["sports"])
def get_event(event_id: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    event = db.get(SportsEvent, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return _event_payload(event)


@app.get("/v1/sports/events/{event_id}/timeline", tags=["sports"])
def get_timeline(event_id: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    event = db.get(SportsEvent, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return {"event_id": event.id, "source_type": event.source_type, "items": event.timeline or []}


@app.get("/v1/sports/events/{event_id}/tactical", tags=["sports"])
def get_tactical(event_id: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    event = db.get(SportsEvent, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return {"event_id": event.id, "source_type": event.source_type, **(event.tactical or {})}


@app.get("/v1/sports/events/{event_id}/stream", tags=["sports"])
async def stream_event_updates(
    event_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Stream real-time tactical ticks and timeline updates via Server-Sent Events (SSE)."""
    event = db.get(SportsEvent, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    async def event_generator():
        try:
            init_data = json.dumps({
                "type": "init",
                "event_id": event.id,
                "score_home": event.score_home,
                "score_away": event.score_away,
                "status": event.status,
                "source_type": event.source_type,
                "timeline_count": len(event.timeline or []),
            })
            yield f"event: match_state\ndata: {init_data}\n\n"

            # Streaming heartbeat and tactical updates
            limit = int(request.query_params.get("ticks", 10))
            interval = float(request.query_params.get("interval", 4.0))
            for tick in range(1, limit + 1):
                if await request.is_disconnected():
                    break
                await asyncio.sleep(interval)
                tick_data = json.dumps({
                    "type": "heartbeat",
                    "tick": tick,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "source_type": event.source_type,
                })
                yield f"event: tick\ndata: {tick_data}\n\n"
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/v1/sessions", tags=["sessions"])
def create_session(payload: SessionCreate, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = _profile_for_user(db, user)
    if payload.event_id and not db.get(SportsEvent, payload.event_id):
        raise HTTPException(status_code=404, detail="Event not found")
    session = ViewingSession(household_id=user["household_id"], profile_id=profile.id, event_id=payload.event_id, mode=payload.mode, context=payload.context)
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"id": session.id, "household_id": session.household_id, "profile_id": session.profile_id, "event_id": session.event_id, "mode": session.mode, "status": session.status, "started_at": session.started_at.isoformat()}


@app.get("/v1/sessions/{session_id}", tags=["sessions"])
def get_session(session_id: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.get(ViewingSession, session_id)
    if not session or session.household_id != user["household_id"]:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"id": session.id, "event_id": session.event_id, "mode": session.mode, "status": session.status, "context": session.context, "started_at": session.started_at.isoformat(), "ended_at": session.ended_at.isoformat() if session.ended_at else None}


@app.patch("/v1/households/{household_id}/preferences", tags=["households"])
def update_preferences(household_id: str, payload: ProfilePreferencesUpdate, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    assert_household_access(user, household_id)
    profile = _profile_for_user(db, user)
    changes = payload.model_dump(exclude_unset=True)
    if "nickname" in changes:
        profile.nickname = changes.pop("nickname")
    profile.preferences = {**(profile.preferences or {}), **changes}
    profile.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"household_id": household_id, "profile_id": profile.id, "nickname": profile.nickname, "preferences": profile.preferences, "updated_at": profile.updated_at.isoformat()}


@app.post("/v1/experience/resolve", tags=["personalization"])
def resolve_experience(payload: ExperienceResolveRequest, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = _profile_for_user(db, user)
    if payload.event_id and not db.get(SportsEvent, payload.event_id):
        raise HTTPException(status_code=404, detail="Event not found")
    prefs = profile.preferences or {}
    scores = {"family": 0.0, "analyst": 0.0, "catch_up": 0.0}
    default = prefs.get("default_mode", "family")
    if default not in scores:
        default = "family"
    scores[default] += 3
    if prefs.get("detail_level") == "advanced":
        scores["analyst"] += 2
    elif prefs.get("detail_level") == "simple":
        scores["family"] += 1
        scores["catch_up"] += 1
    if prefs.get("spoiler_policy") == "strict":
        scores["catch_up"] += 1
    if payload.override_mode:
        selected = payload.override_mode
        reason = "User override takes priority over personalization suggestions."
    else:
        selected = max(scores, key=scores.get)
        reason = f"Suggested from saved preferences: default_mode={default}, detail_level={prefs.get('detail_level', 'balanced')}."
    return {"mode": selected, "scores": scores, "reason": reason, "is_suggestion": payload.override_mode is None, "source_type": "profile_preferences"}


@app.post("/v1/ai/commands", tags=["ai"])
async def ai_command(payload: AICommandRequest, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = _profile_for_user(db, user)
    event = db.get(SportsEvent, payload.event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return await analyze_command(db, household_id=user["household_id"], profile=profile, text=payload.text, event=event, session_id=payload.session_id, selected_player_id=payload.selected_player_id, idempotency_key=payload.idempotency_key)


@app.post("/v1/coach/sessions", tags=["coach"])
def create_coach_session(payload: CoachSessionCreate, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    if not payload.consent_recorded:
        raise HTTPException(status_code=400, detail="Explicit camera and metrics consent is required")
    profile = _profile_for_user(db, user)
    session = CoachSession(household_id=user["household_id"], profile_id=profile.id, exercise=payload.exercise, consent_recorded=True)
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"id": session.id, "exercise": session.exercise, "status": session.status, "consent_recorded": session.consent_recorded, "started_at": session.started_at.isoformat(), "raw_media_stored": False}


@app.post("/v1/coach/sessions/{session_id}/metrics", tags=["coach"])
def add_coach_metric(session_id: str, payload: CoachMetricCreate, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.get(CoachSession, session_id)
    if not session or session.household_id != user["household_id"]:
        raise HTTPException(status_code=404, detail="Coaching session not found")
    if session.status != "active" or not session.consent_recorded:
        raise HTTPException(status_code=409, detail="Coaching session is not active")
    metric = CoachMetric(coach_session_id=session.id, metric_type=payload.metric_type, value=payload.value, unit=payload.unit, confidence=payload.confidence)
    session.metrics_count += 1
    db.add(metric)
    db.commit()
    return {"accepted": True, "session_id": session.id, "metrics_count": session.metrics_count, "raw_media_stored": False}


@app.patch("/v1/coach/sessions/{session_id}/complete", tags=["coach"])
def complete_coach_session(session_id: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.get(CoachSession, session_id)
    if not session or session.household_id != user["household_id"]:
        raise HTTPException(status_code=404, detail="Coaching session not found")
    if session.status != "active":
        raise HTTPException(status_code=409, detail="Coaching session is already complete")
    session.status = "completed"
    session.ended_at = datetime.now(timezone.utc)
    session.summary = {"metrics_count": session.metrics_count, "note": "Summary uses submitted derived metrics only; it is not a medical assessment."}
    db.commit()
    return {"id": session.id, "status": session.status, "summary": session.summary, "ended_at": session.ended_at.isoformat()}


@app.post("/v1/feedback", tags=["feedback"])
def create_feedback(payload: FeedbackCreate, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    feedback = Feedback(household_id=user["household_id"], category=payload.category, message=payload.message, context=payload.context)
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return {"id": feedback.id, "status": "received", "created_at": feedback.created_at.isoformat()}


@app.delete("/v1/me/data", tags=["privacy"])
def delete_my_data(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    household_id = user["household_id"]
    db.query(CoachMetric).filter(CoachMetric.coach_session_id.in_(select(CoachSession.id).where(CoachSession.household_id == household_id))).delete(synchronize_session=False)
    db.query(CoachSession).filter(CoachSession.household_id == household_id).delete(synchronize_session=False)
    db.query(AnalysisRecord).filter(AnalysisRecord.household_id == household_id).delete(synchronize_session=False)
    db.query(Feedback).filter(Feedback.household_id == household_id).delete(synchronize_session=False)
    db.query(ViewingSession).filter(ViewingSession.household_id == household_id).delete(synchronize_session=False)
    db.query(Profile).filter(Profile.household_id == household_id).delete(synchronize_session=False)
    db.query(Household).filter(Household.id == household_id).delete(synchronize_session=False)
    db.commit()
    return {"status": "deleted", "deleted_scope": "household application data", "note": "Operational logs and external-provider data follow their own retention policies."}
