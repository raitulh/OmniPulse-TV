from typing import Any
import hashlib

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AnalysisRecord, Profile, SportsEvent, ViewingSession
from app.services.llm_provider import generate_grounded_explanation_async


def _record_response(record: AnalysisRecord, event: SportsEvent, *, replay: bool) -> dict[str, Any]:
    payload = record.payload or {}
    player_ids = payload.get("node_ids", [])
    nodes = [player for player in (event.tactical or {}).get("players", []) if player.get("id") in player_ids]
    return {
        "command_id": record.id,
        "intent": record.intent,
        "mode": "analyst" if record.intent != "catch_up" else "catch_up",
        "source_type": record.source_type,
        "provider": record.provider,
        "analysis": {"summary": record.summary, "player_ids": player_ids},
        "visualization": {"type": "tactical_nodes", "focus_id": payload.get("selected_player_id"), "nodes": nodes},
        "created_at": record.created_at.isoformat(),
        "idempotent_replay": replay,
    }


async def analyze_command(
    db: Session,
    *,
    household_id: str,
    profile: Profile,
    text: str,
    event: SportsEvent,
    session_id: str | None,
    selected_player_id: str | None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    if session_id:
        session = db.get(ViewingSession, session_id)
        if not session or session.household_id != household_id:
            raise HTTPException(status_code=404, detail="Viewing session not found")
        if session.event_id and session.event_id != event.id:
            raise HTTPException(status_code=409, detail="Viewing session belongs to a different event")

    request_fingerprint = hashlib.sha256(f"{event.id}|{session_id or ''}|{selected_player_id or ''}|{text.strip()}".encode("utf-8")).hexdigest()
    if idempotency_key:
        previous = db.scalar(select(AnalysisRecord).where(
            AnalysisRecord.household_id == household_id,
            AnalysisRecord.idempotency_key == idempotency_key,
        ))
        if previous:
            if previous.event_id != event.id or (previous.payload or {}).get("request_fingerprint") != request_fingerprint:
                raise HTTPException(status_code=409, detail="Idempotency key was already used for a different command")
            return _record_response(previous, event, replay=True)

    tactical = event.tactical or {}
    players = tactical.get("players", [])
    player = next((p for p in players if p.get("id") == selected_player_id), None) if selected_player_id else None
    if selected_player_id and not player:
        raise HTTPException(status_code=422, detail="Selected player does not belong to this event")

    lowered = text.casefold()
    if any(word in lowered for word in ("catch me up", "summary", "what did i miss")):
        intent = "catch_up"
        summary = f"This is a sample-data recap of {event.title}. The sample timeline contains {len(event.timeline or [])} events."
        nodes = []
    elif player or any(word in lowered for word in ("player", "who is", "speed", "break down", "breakdown", "analyze", "analyse", "play")):
        intent = "break_down_play"
        if player:
            summary = (
                f"{player['name']} plays as {player.get('role', 'player')} for {player.get('team', 'the team')}. "
                f"The sample tactical feed lists {player.get('speed_kph', 0)} km/h; this is illustrative sample data, not a live measurement."
            )
            nodes = [player]
        else:
            summary = "The sample sequence links a progressive pass from player 07 to player 12, with player 18 shown as a possible wide option. These are illustrative sample events, not live match tracking."
            nodes = players[:3]
    else:
        intent = "help"
        summary = "Try: 'Break down this play', 'Who is player 07?', or 'Catch me up'."
        nodes = []

    explanation, provider = await generate_grounded_explanation_async(
        intent=intent,
        user_text=text,
        event={"id": event.id, "sport": event.sport, "league": event.league, "title": event.title, "home_team": event.home_team, "away_team": event.away_team, "source_type": event.source_type},
        players=players,
        timeline=event.timeline or [],
    )
    if explanation:
        summary = explanation

    record = AnalysisRecord(
        household_id=household_id,
        profile_id=profile.id,
        event_id=event.id,
        idempotency_key=idempotency_key,
        intent=intent,
        source_type=event.source_type,
        provider=provider,
        summary=summary,
        payload={"selected_player_id": selected_player_id, "node_ids": [p["id"] for p in nodes], "request_fingerprint": request_fingerprint},
    )
    db.add(record)
    try:
        db.commit()
        db.refresh(record)
        return _record_response(record, event, replay=False)
    except IntegrityError:
        db.rollback()
        # A simultaneous request with the same idempotency key can win the unique-key race.
        # Return its stored result rather than a 500; a conflicting payload receives 409.
        if idempotency_key:
            previous = db.scalar(select(AnalysisRecord).where(
                AnalysisRecord.household_id == household_id,
                AnalysisRecord.idempotency_key == idempotency_key,
            ))
            if previous:
                if previous.event_id != event.id or (previous.payload or {}).get("request_fingerprint") != request_fingerprint:
                    raise HTTPException(status_code=409, detail="Idempotency key was already used for a different command")
                return _record_response(previous, event, replay=True)
        raise
