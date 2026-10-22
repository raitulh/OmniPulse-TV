"""Initial OmniPulse schema with explicit DDL and indexes.

Revision ID: 0001_initial
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "households",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False, server_default="My Household"),
        sa.Column("owner_sub", sa.String(length=160), nullable=False),
        sa.Column("preferences", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_sub", name="uq_households_owner_sub"),
    )
    op.create_index("ix_households_owner_sub", "households", ["owner_sub"])

    op.create_table(
        "profiles",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("household_id", sa.String(length=80), sa.ForeignKey("households.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nickname", sa.String(length=80), nullable=False, server_default="Viewer"),
        sa.Column("profile_type", sa.String(length=30), nullable=False, server_default="personal"),
        sa.Column("preferences", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("household_id", "id", name="uq_profiles_household_id"),
    )
    op.create_index("ix_profiles_household_id", "profiles", ["household_id"])

    op.create_table(
        "sports_events",
        sa.Column("id", sa.String(length=100), primary_key=True),
        sa.Column("sport", sa.String(length=30), nullable=False),
        sa.Column("league", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("home_team", sa.String(length=100), nullable=False),
        sa.Column("away_team", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="sample"),
        sa.Column("source_type", sa.String(length=30), nullable=False, server_default="sample"),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("score_home", sa.Integer(), nullable=True),
        sa.Column("score_away", sa.Integer(), nullable=True),
        sa.Column("timeline", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("tactical", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sports_events_sport", "sports_events", ["sport"])

    op.create_table(
        "viewing_sessions",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("household_id", sa.String(length=80), sa.ForeignKey("households.id", ondelete="CASCADE"), nullable=False),
        sa.Column("profile_id", sa.String(length=80), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_id", sa.String(length=100), nullable=True),
        sa.Column("mode", sa.String(length=30), nullable=False, server_default="family"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("context", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_viewing_sessions_household_id", "viewing_sessions", ["household_id"])
    op.create_index("ix_viewing_sessions_profile_id", "viewing_sessions", ["profile_id"])

    op.create_table(
        "analysis_records",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("household_id", sa.String(length=80), sa.ForeignKey("households.id", ondelete="CASCADE"), nullable=False),
        sa.Column("profile_id", sa.String(length=80), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_id", sa.String(length=100), sa.ForeignKey("sports_events.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=True),
        sa.Column("intent", sa.String(length=80), nullable=False),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False, server_default="rules"),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("household_id", "idempotency_key", name="uq_analysis_household_idempotency"),
    )
    op.create_index("ix_analysis_records_household_id", "analysis_records", ["household_id"])
    op.create_index("ix_analysis_records_profile_id", "analysis_records", ["profile_id"])
    op.create_index("ix_analysis_records_event_id", "analysis_records", ["event_id"])

    op.create_table(
        "coach_sessions",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("household_id", sa.String(length=80), sa.ForeignKey("households.id", ondelete="CASCADE"), nullable=False),
        sa.Column("profile_id", sa.String(length=80), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("exercise", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("consent_recorded", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("metrics_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("summary", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_coach_sessions_household_id", "coach_sessions", ["household_id"])
    op.create_index("ix_coach_sessions_profile_id", "coach_sessions", ["profile_id"])

    op.create_table(
        "coach_metrics",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("coach_session_id", sa.String(length=80), sa.ForeignKey("coach_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("metric_type", sa.String(length=80), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=30), nullable=False, server_default="unitless"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_coach_metrics_coach_session_id", "coach_metrics", ["coach_session_id"])

    op.create_table(
        "feedback",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("household_id", sa.String(length=80), sa.ForeignKey("households.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("context", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_feedback_household_id", "feedback", ["household_id"])

    op.create_table(
        "device_auth_sessions",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("device_code", sa.String(length=120), nullable=False),
        sa.Column("user_code", sa.String(length=20), nullable=False),
        sa.Column("client_id", sa.String(length=80), nullable=False, server_default="omnipulse-tv-client"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("subject", sa.String(length=160), nullable=True),
        sa.Column("household_id", sa.String(length=80), nullable=True),
        sa.Column("profile_id", sa.String(length=80), nullable=True),
        sa.Column("interval", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_device_auth_sessions_device_code", "device_auth_sessions", ["device_code"], unique=True)
    op.create_index("ix_device_auth_sessions_user_code", "device_auth_sessions", ["user_code"], unique=True)


def downgrade() -> None:
    op.drop_table("device_auth_sessions")
    op.drop_table("feedback")
    op.drop_table("coach_metrics")
    op.drop_table("coach_sessions")
    op.drop_table("analysis_records")
    op.drop_table("viewing_sessions")
    op.drop_table("sports_events")
    op.drop_table("profiles")
    op.drop_table("households")
