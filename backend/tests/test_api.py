def get_token(client):
    response = client.post("/v1/auth/demo")
    assert response.status_code == 200
    return response.json()["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_health_and_demo_auth(client):
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").json()["status"] == "ready"
    token = get_token(client)
    assert client.get("/v1/me", headers=auth(token)).status_code == 200


def test_protected_routes_require_token(client):
    assert client.get("/v1/sports/events").status_code == 401


def test_list_events_and_tactical_data(client):
    token = get_token(client)
    events = client.get("/v1/sports/events", headers=auth(token))
    assert events.status_code == 200
    data = events.json()
    assert data["count"] >= 1
    assert all(item["source_type"] == "sample" for item in data["items"])
    event_id = data["items"][0]["id"]
    tactical = client.get(f"/v1/sports/events/{event_id}/tactical", headers=auth(token))
    assert tactical.status_code == 200
    assert len(tactical.json()["players"]) > 0


def test_session_preferences_and_personalization(client):
    token = get_token(client)
    headers = auth(token)
    me = client.get("/v1/me", headers=headers).json()
    household_id = me["household"]["id"]
    profile_id = me["profile"]["id"]
    patch = client.patch(f"/v1/households/{household_id}/preferences", headers=headers, json={"default_mode": "analyst", "detail_level": "advanced"})
    assert patch.status_code == 200
    session = client.post("/v1/sessions", headers=headers, json={"event_id": "demo-football-001", "mode": "analyst"})
    assert session.status_code == 200
    resolve = client.post("/v1/experience/resolve", headers=headers, json={"event_id": "demo-football-001"})
    assert resolve.status_code == 200
    assert resolve.json()["mode"] == "analyst"
    assert profile_id == session.json()["profile_id"]


def test_ai_command_validates_player_id_and_marks_source(client):
    token = get_token(client)
    headers = auth(token)
    result = client.post("/v1/ai/commands", headers=headers, json={"event_id": "demo-football-001", "text": "Break down this play"})
    assert result.status_code == 200
    body = result.json()
    assert body["source_type"] == "sample"
    assert body["provider"] == "rules"
    invalid = client.post("/v1/ai/commands", headers=headers, json={"event_id": "demo-football-001", "text": "Who is this player?", "selected_player_id": "made-up-player"})
    assert invalid.status_code == 422


def test_household_isolation(client):
    token = get_token(client)
    headers = auth(token)
    forbidden = client.patch("/v1/households/someone-elses-household/preferences", headers=headers, json={"default_mode": "family"})
    assert forbidden.status_code == 404


def test_coach_requires_consent_and_accepts_derived_metrics(client):
    token = get_token(client)
    headers = auth(token)
    denied = client.post("/v1/coach/sessions", headers=headers, json={"exercise": "squat", "consent_recorded": False})
    assert denied.status_code == 400
    created = client.post("/v1/coach/sessions", headers=headers, json={"exercise": "squat", "consent_recorded": True})
    assert created.status_code == 200
    session_id = created.json()["id"]
    metric = client.post(f"/v1/coach/sessions/{session_id}/metrics", headers=headers, json={"metric_type": "knee_angle", "value": 94, "unit": "degrees", "confidence": 0.91})
    assert metric.status_code == 200
    assert metric.json()["raw_media_stored"] is False
    complete = client.patch(f"/v1/coach/sessions/{session_id}/complete", headers=headers)
    assert complete.status_code == 200
    assert complete.json()["status"] == "completed"


def test_validation_and_not_found(client):
    token = get_token(client)
    headers = auth(token)
    invalid = client.post("/v1/sessions", headers=headers, json={"mode": "unicorn"})
    assert invalid.status_code == 422
    missing = client.get("/v1/sports/events/not-a-real-event", headers=headers)
    assert missing.status_code == 404


def test_feedback_and_data_deletion(client):
    token = get_token(client)
    headers = auth(token)
    feedback = client.post("/v1/feedback", headers=headers, json={"category": "ux", "message": "Focus outline could be brighter."})
    assert feedback.status_code == 200
    deleted = client.delete("/v1/me/data", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "deleted"
    assert client.get("/v1/me", headers=headers).status_code == 403


def test_analysis_idempotency_replays_same_result(client):
    token = get_token(client)
    headers = auth(token)
    payload = {"event_id": "demo-football-001", "text": "Break down this play", "idempotency_key": "xray-command-001"}
    first = client.post("/v1/ai/commands", headers=headers, json=payload)
    second = client.post("/v1/ai/commands", headers=headers, json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["command_id"] == second.json()["command_id"]
    assert first.json()["idempotent_replay"] is False
    assert second.json()["idempotent_replay"] is True
    conflicting = client.post("/v1/ai/commands", headers=headers, json={"event_id": "demo-football-001", "text": "Catch me up", "idempotency_key": "xray-command-001"})
    assert conflicting.status_code == 409


def test_onboarding_provisions_cognito_style_identity(client):
    from datetime import datetime, timedelta, timezone
    import jwt
    from app.core.config import get_settings

    settings = get_settings()
    now = datetime.now(timezone.utc)
    token = jwt.encode({"sub": "new-cognito-subject", "iss": settings.jwt_issuer, "iat": now, "exp": now + timedelta(minutes=10)}, settings.jwt_secret, algorithm="HS256")
    headers = auth(token)
    onboarded = client.post("/v1/onboarding", headers=headers, json={})
    assert onboarded.status_code == 200
    assert onboarded.json()["created"] is True
    profile = client.get("/v1/me", headers=headers)
    assert profile.status_code == 200
    assert profile.json()["household"]["id"] == onboarded.json()["household_id"]


def test_ai_rejects_viewing_session_for_different_event(client):
    from copy import deepcopy
    from app.db.session import SessionLocal
    from app.models import SportsEvent
    from app.services.sample_data import SAMPLE_EVENT

    token = get_token(client)
    headers = auth(token)
    session_response = client.post(
        "/v1/sessions", headers=headers, json={"event_id": "demo-football-001", "mode": "analyst"}
    )
    assert session_response.status_code == 200
    second_event_payload = deepcopy(SAMPLE_EVENT)
    second_event_payload["id"] = "demo-football-002"
    second_event_payload["title"] = "Harbor United vs East Town (sample)"
    second_event_payload["home_team"] = "Harbor United"
    second_event_payload["away_team"] = "East Town"
    with SessionLocal() as db:
        db.add(SportsEvent(**second_event_payload))
        db.commit()
    response = client.post(
        "/v1/ai/commands",
        headers=headers,
        json={
            "event_id": "demo-football-002",
            "text": "Break down this play",
            "session_id": session_response.json()["id"],
        },
    )
    assert response.status_code == 409


def test_production_settings_reject_insecure_defaults():
    import pytest
    from app.core.config import Settings

    with pytest.raises(RuntimeError, match="DEMO_MODE"):
        Settings(environment="production", demo_mode=True).validate_for_startup()

    safe_base = {
        "environment": "production",
        "demo_mode": False,
        "database_url": "postgresql+psycopg://user:password@db.example:5432/omnipulse",
        "cognito_user_pool_id": "us-east-1_example",
        "cognito_app_client_id": "example-client",
        "cors_origins": "https://app.example.com",
        "jwt_secret": "local-only-change-me-before-deployment",
    }
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        Settings(**safe_base).validate_for_startup()

    unsafe_cors = {**safe_base, "jwt_secret": "a-strong-test-secret-that-is-more-than-32-chars", "cors_origins": "*"}
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        Settings(**unsafe_cors).validate_for_startup()


def test_validation_error_has_request_id_and_safe_envelope(client):
    token = get_token(client)
    response = client.post(
        "/v1/sessions",
        headers={**auth(token), "X-Request-ID": "test-request-validation-01"},
        json={"mode": "unicorn"},
    )
    assert response.status_code == 422
    assert response.headers["X-Request-ID"] == "test-request-validation-01"
    assert response.json()["error"]["request_id"] == "test-request-validation-01"
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "traceback" not in response.text.lower()


def test_oversized_content_length_returns_safe_413(client):
    token = get_token(client)
    # Test the middleware with an explicit oversized Content-Length; no large allocation is needed.
    response = client.post(
        "/v1/feedback",
        headers={**auth(token), "Content-Length": "130000", "X-Request-ID": "test-too-large-01"},
        json={"category": "ux", "message": "test"},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "REQUEST_TOO_LARGE"
    assert response.json()["error"]["request_id"] == "test-too-large-01"
