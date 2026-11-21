"""Modelli SQLAlchemy. Su Postgres le colonne embedding usano pgvector."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import (JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, false,
                        UniqueConstraint, create_engine)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import get_settings
from .embeddings import EMB_DIM

settings = get_settings()

if settings.is_postgres:
    from pgvector.sqlalchemy import Vector
    EmbeddingType = Vector(EMB_DIM)
else:  # SQLite (test): lista JSON, similarita' calcolata in Python
    EmbeddingType = JSON

_connect_args: dict = {}
_kwargs: dict = {}
if settings.database_url.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}
    if ":memory:" in settings.database_url:
        _kwargs["poolclass"] = StaticPool
engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=_connect_args, **_kwargs)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Athlete(Base):
    __tablename__ = "athletes"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    profile: Mapped[str] = mapped_column(String(32), default="standard")  # standard|paralympic|master
    consent_data: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_alerts: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(16), index=True)  # athlete|clinician|admin
    is_demo_guest: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class AthleteAccess(Base):
    __tablename__ = "athlete_access"
    __table_args__ = (UniqueConstraint("user_id", "athlete_id", name="uq_user_athlete_access"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    athlete_id: Mapped[str] = mapped_column(ForeignKey("athletes.id", ondelete="CASCADE"), index=True)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class ConsentEvent(Base):
    __tablename__ = "consent_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    athlete_id: Mapped[str] = mapped_column(ForeignKey("athletes.id", ondelete="CASCADE"), index=True)
    actor_user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    consent_type: Mapped[str] = mapped_column(String(32))  # data_processing|clinician_alerts
    version: Mapped[str] = mapped_column(String(80))
    granted: Mapped[bool] = mapped_column(Boolean)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class WearableSyncState(Base):
    __tablename__ = "wearable_sync_states"
    __table_args__ = (UniqueConstraint("athlete_id", "provider", name="uq_athlete_wearable_provider"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    athlete_id: Mapped[str] = mapped_column(ForeignKey("athletes.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(48))
    cursor_day: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="never")
    last_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_success_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    records_received: Mapped[int] = mapped_column(Integer, default=0)
    records_accepted: Mapped[int] = mapped_column(Integer, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class DailyMetric(Base):
    __tablename__ = "daily_metrics"
    __table_args__ = (UniqueConstraint("athlete_id", "day", name="uq_athlete_day"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    athlete_id: Mapped[str] = mapped_column(ForeignKey("athletes.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    rmssd_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    resting_hr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    hr_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sleep_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sleep_efficiency: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    spo2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    skin_temp_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rpe: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    duration_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    doms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    load: Mapped[float] = mapped_column(Float, default=0.0)


class MemoryNote(Base):
    """Memoria a lungo termine: adattamenti, preferenze, sintesi delle interazioni."""
    __tablename__ = "memory_notes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    athlete_id: Mapped[str] = mapped_column(ForeignKey("athletes.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    kind: Mapped[str] = mapped_column(String(24))  # adaptation|preference|interaction|summary
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[Optional[list]] = mapped_column(EmbeddingType, nullable=True)


class KnowledgeDoc(Base):
    """Base di conoscenza per la RAG scientifica."""
    __tablename__ = "knowledge_docs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(300))
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[Optional[list]] = mapped_column(EmbeddingType, nullable=True)


class HitlCase(Base):
    """Caso in attesa di validazione da parte di medico o preparatore."""
    __tablename__ = "hitl_cases"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    athlete_id: Mapped[str] = mapped_column(ForeignKey("athletes.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|approved|modified|rejected
    trigger: Mapped[str] = mapped_column(String(64))
    level: Mapped[str] = mapped_column(String(12))
    report: Mapped[dict] = mapped_column(JSON)
    draft_text: Mapped[str] = mapped_column(Text)
    final_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewer: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    reviewer_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class AlertLog(Base):
    __tablename__ = "alert_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    athlete_id: Mapped[str] = mapped_column(ForeignKey("athletes.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    channel: Mapped[str] = mapped_column(String(16))
    body: Mapped[str] = mapped_column(Text)
    simulated: Mapped[bool] = mapped_column(Boolean, default=True)


def init_db() -> None:
    if settings.app_env == "test":
        Base.metadata.create_all(engine)
