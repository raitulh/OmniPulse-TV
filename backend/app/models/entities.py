from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:16]}"


class Household(Base):
    __tablename__ = "households"

    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=lambda: new_id("hh"))
    name: Mapped[str] = mapped_column(String(100), default="My Household")
    owner_sub: Mapped[str] = mapped_column(String(160), index=True, unique=True)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    profiles: Mapped[list["Profile"]] = relationship(back_populates="household", cascade="all, delete-orphan")


class Profile(Base):
    __tablename__ = "profiles"
    __table_args__ = (UniqueConstraint("household_id", "id"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=lambda: new_id("profile"))
    household_id: Mapped[str] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    nickname: Mapped[str] = mapped_column(String(80), default="Viewer")
    profile_type: Mapped[str] = mapped_column(String(30), default="personal")
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    household: Mapped[Household] = relationship(back_populates="profiles")


class ViewingSession(Base):
    __tablename__ = "viewing_sessions"

    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=lambda: new_id("view"))
    household_id: Mapped[str] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    profile_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    event_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mode: Mapped[str] = mapped_column(String(30), default="family")
    status: Mapped[str] = mapped_column(String(30), default="active")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    context: Mapped[dict] = mapped_column(JSON, default=dict)


class SportsEvent(Base):
    __tablename__ = "sports_events"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    sport: Mapped[str] = mapped_column(String(30), index=True)
    league: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(180))
    home_team: Mapped[str] = mapped_column(String(100))
    away_team: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), default="sample")
    source_type: Mapped[str] = mapped_column(String(30), default="sample")
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    score_home: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_away: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timeline: Mapped[list] = mapped_column(JSON, default=list)
    tactical: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AnalysisRecord(Base):
    __tablename__ = "analysis_records"
    __table_args__ = (UniqueConstraint("household_id", "idempotency_key", name="uq_analysis_household_idempotency"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=lambda: new_id("analysis"))
    household_id: Mapped[str] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    profile_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("sports_events.id"), index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    intent: Mapped[str] = mapped_column(String(80))
    source_type: Mapped[str] = mapped_column(String(30))
    provider: Mapped[str] = mapped_column(String(50), default="rules")
    summary: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CoachSession(Base):
    __tablename__ = "coach_sessions"

    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=lambda: new_id("coach"))
    household_id: Mapped[str] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    profile_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    exercise: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(30), default="active")
    consent_recorded: Mapped[bool] = mapped_column(Boolean, default=False)
    metrics_count: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CoachMetric(Base):
    __tablename__ = "coach_metrics"

    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=lambda: new_id("metric"))
    coach_session_id: Mapped[str] = mapped_column(ForeignKey("coach_sessions.id", ondelete="CASCADE"), index=True)
    metric_type: Mapped[str] = mapped_column(String(80))
    value: Mapped[float] = mapped_column()
    unit: Mapped[str] = mapped_column(String(30), default="unitless")
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=lambda: new_id("feedback"))
    household_id: Mapped[str] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(50))
    message: Mapped[str] = mapped_column(Text)
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DeviceAuthSession(Base):
    __tablename__ = "device_auth_sessions"

    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=lambda: new_id("dev"))
    device_code: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    user_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    client_id: Mapped[str] = mapped_column(String(80), default="omnipulse-tv-client")
    status: Mapped[str] = mapped_column(String(30), default="pending")  # pending, authorized, denied, expired
    subject: Mapped[str | None] = mapped_column(String(160), nullable=True)
    household_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    profile_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    interval: Mapped[int] = mapped_column(Integer, default=5)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

