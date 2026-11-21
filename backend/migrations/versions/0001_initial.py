"""Initial BioPulse schema.

Revision ID: 0001_initial
Revises:
"""
from alembic import op
import pgvector.sqlalchemy
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "athletes",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("profile", sa.String(32), nullable=False),
        sa.Column("consent_data", sa.Boolean(), nullable=False),
        sa.Column("consent_alerts", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_role", "users", ["role"])
    op.create_table(
        "athlete_access",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("athlete_id", sa.String(64), sa.ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("user_id", "athlete_id", name="uq_user_athlete_access"),
    )
    op.create_index("ix_athlete_access_user_id", "athlete_access", ["user_id"])
    op.create_index("ix_athlete_access_athlete_id", "athlete_access", ["athlete_id"])
    op.create_table(
        "auth_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("csrf_hash", sa.String(64), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])
    op.create_table(
        "consent_events",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("athlete_id", sa.String(64), sa.ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("consent_type", sa.String(32), nullable=False),
        sa.Column("version", sa.String(80), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_consent_events_athlete_id", "consent_events", ["athlete_id"])
    op.create_index("ix_consent_events_changed_at", "consent_events", ["changed_at"])
    op.create_table(
        "wearable_sync_states",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("athlete_id", sa.String(64), sa.ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(48), nullable=False),
        sa.Column("cursor_day", sa.Date()),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("records_received", sa.Integer(), nullable=False),
        sa.Column("records_accepted", sa.Integer(), nullable=False),
        sa.Column("rejected_count", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text()),
        sa.UniqueConstraint("athlete_id", "provider", name="uq_athlete_wearable_provider"),
    )
    op.create_index("ix_wearable_sync_states_athlete_id", "wearable_sync_states", ["athlete_id"])
    op.create_table(
        "daily_metrics",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("athlete_id", sa.String(64), sa.ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("rmssd_ms", sa.Float()),
        sa.Column("resting_hr", sa.Float()),
        sa.Column("hr_max", sa.Float()),
        sa.Column("sleep_hours", sa.Float()),
        sa.Column("sleep_efficiency", sa.Float()),
        sa.Column("spo2", sa.Float()),
        sa.Column("skin_temp_c", sa.Float()),
        sa.Column("rpe", sa.Float()),
        sa.Column("duration_min", sa.Float()),
        sa.Column("doms", sa.Float()),
        sa.Column("load", sa.Float(), nullable=False),
        sa.UniqueConstraint("athlete_id", "day", name="uq_athlete_day"),
    )
    op.create_index("ix_daily_metrics_athlete_id", "daily_metrics", ["athlete_id"])
    op.create_index("ix_daily_metrics_day", "daily_metrics", ["day"])
    op.create_table(
        "memory_notes",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("athlete_id", sa.String(64), sa.ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(256)),
    )
    op.create_index("ix_memory_notes_athlete_id", "memory_notes", ["athlete_id"])
    op.create_table(
        "knowledge_docs",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("slug", sa.String(80), nullable=False, unique=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("source", sa.String(300), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(256)),
    )
    op.create_table(
        "hitl_cases",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("athlete_id", sa.String(64), sa.ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("trigger", sa.String(64), nullable=False),
        sa.Column("level", sa.String(12), nullable=False),
        sa.Column("report", sa.JSON(), nullable=False),
        sa.Column("draft_text", sa.Text(), nullable=False),
        sa.Column("final_text", sa.Text()),
        sa.Column("reviewer", sa.String(120)),
        sa.Column("reviewer_note", sa.Text()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_hitl_cases_athlete_id", "hitl_cases", ["athlete_id"])
    op.create_table(
        "alert_log",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("athlete_id", sa.String(64), sa.ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("simulated", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_alert_log_athlete_id", "alert_log", ["athlete_id"])


def downgrade() -> None:
    op.drop_index("ix_alert_log_athlete_id", table_name="alert_log")
    op.drop_table("alert_log")
    op.drop_index("ix_hitl_cases_athlete_id", table_name="hitl_cases")
    op.drop_table("hitl_cases")
    op.drop_table("knowledge_docs")
    op.drop_index("ix_memory_notes_athlete_id", table_name="memory_notes")
    op.drop_table("memory_notes")
    op.drop_index("ix_daily_metrics_day", table_name="daily_metrics")
    op.drop_index("ix_daily_metrics_athlete_id", table_name="daily_metrics")
    op.drop_table("daily_metrics")
    op.drop_index("ix_wearable_sync_states_athlete_id", table_name="wearable_sync_states")
    op.drop_table("wearable_sync_states")
    op.drop_index("ix_consent_events_changed_at", table_name="consent_events")
    op.drop_index("ix_consent_events_athlete_id", table_name="consent_events")
    op.drop_table("consent_events")
    op.drop_index("ix_auth_sessions_expires_at", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_index("ix_athlete_access_athlete_id", table_name="athlete_access")
    op.drop_index("ix_athlete_access_user_id", table_name="athlete_access")
    op.drop_table("athlete_access")
    op.drop_index("ix_users_role", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.drop_table("athletes")
