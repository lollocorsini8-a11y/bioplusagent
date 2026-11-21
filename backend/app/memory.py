"""Memoria a breve termine (Redis, con fallback in-process) e a lungo termine (DB + vettori)."""
from __future__ import annotations

import json
import logging
from collections import defaultdict, deque
from typing import Optional

import redis
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import (AlertLog, Athlete, AthleteAccess, AuthSession, ConsentEvent, DailyMetric, HitlCase,
                 MemoryNote, KnowledgeDoc, User, WearableSyncState)
from .embeddings import cosine, embed

log = logging.getLogger("biopulse.memory")
SHORT_TTL_S = 24 * 3600
SHORT_MAX = 20


class ShortTermMemory:
    """Ultimi turni di conversazione. Redis se raggiungibile, altrimenti memoria di processo."""

    def __init__(self) -> None:
        self._local: dict[str, deque] = defaultdict(lambda: deque(maxlen=SHORT_MAX))
        self._redis = None
        url = get_settings().redis_url
        if url:
            try:
                import redis
                r = redis.Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1, decode_responses=True)
                r.ping()
                self._redis = r
            except Exception as exc:  # noqa: BLE001
                log.warning("Redis non disponibile (%s): uso memoria in-process.", exc)

    @property
    def backend(self) -> str:
        return "redis" if self._redis else "in-process"

    def append(self, athlete_id: str, role: str, content: str) -> None:
        item = json.dumps({"role": role, "content": content[:1500]}, ensure_ascii=False)
        if self._redis:
            try:
                key = f"stm:{athlete_id}"
                self._redis.rpush(key, item)
                self._redis.ltrim(key, -SHORT_MAX, -1)
                self._redis.expire(key, SHORT_TTL_S)
                return
            except Exception as exc:  # noqa: BLE001
                log.warning("Redis in errore (%s): passo a memoria in-process.", exc)
                self._redis = None
        self._local[athlete_id].append(json.loads(item))

    def get(self, athlete_id: str, n: int = 6) -> list[dict]:
        if self._redis:
            try:
                return [json.loads(x) for x in self._redis.lrange(f"stm:{athlete_id}", -n, -1)]
            except Exception:  # noqa: BLE001
                self._redis = None
        return list(self._local[athlete_id])[-n:]

    def clear(self, athlete_id: str) -> None:
        self._local.pop(athlete_id, None)
        url = get_settings().redis_url
        if not url:
            return
        try:
            client = self._redis
            if client is None:
                client = redis.Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)
            client.delete(f"stm:{athlete_id}")
            self._redis = client
        except redis.RedisError as exc:
            log.exception("Impossibile cancellare la memoria Redis dell'atleta.")
            raise RuntimeError("Cancellazione della memoria Redis non completata.") from exc


short_term = ShortTermMemory()


def remember(session: Session, athlete_id: str, kind: str, text: str) -> MemoryNote:
    note = MemoryNote(athlete_id=athlete_id, kind=kind, text=text, embedding=embed(text))
    session.add(note)
    session.commit()
    return note


def recall(session: Session, athlete_id: str, query: str, k: int = 3) -> list[MemoryNote]:
    """Richiamo semantico dallo storico dell'atleta."""
    notes = session.scalars(select(MemoryNote).where(MemoryNote.athlete_id == athlete_id)).all()
    if not notes:
        return []
    q = embed(query)
    notes = [n for n in notes if n.embedding is not None]
    notes.sort(key=lambda n: cosine(q, list(n.embedding)), reverse=True)
    top = notes[:k]
    return sorted(top, key=lambda n: n.created_at)


def search_knowledge(session: Session, query: str, k: int = 3) -> list[KnowledgeDoc]:
    q = embed(query)
    if get_settings().is_postgres:
        return list(session.scalars(
            select(KnowledgeDoc).order_by(KnowledgeDoc.embedding.cosine_distance(q)).limit(k)))
    docs = session.scalars(select(KnowledgeDoc)).all()
    docs.sort(key=lambda d: cosine(q, list(d.embedding)), reverse=True)
    return docs[:k]


def erase(session: Session, athlete_id: str, scope: str = "memory") -> dict:
    """Diritto alla cancellazione (GDPR art. 17). scope: memory | all."""
    n_notes = session.execute(delete(MemoryNote).where(MemoryNote.athlete_id == athlete_id)).rowcount
    out = {"memory_notes_deleted": n_notes}
    if scope == "all":
        out["metrics_deleted"] = session.execute(delete(DailyMetric).where(DailyMetric.athlete_id == athlete_id)).rowcount
        out["cases_deleted"] = session.execute(delete(HitlCase).where(HitlCase.athlete_id == athlete_id)).rowcount
        out["alerts_deleted"] = session.execute(delete(AlertLog).where(AlertLog.athlete_id == athlete_id)).rowcount
        out["consent_events_deleted"] = session.execute(
            delete(ConsentEvent).where(ConsentEvent.athlete_id == athlete_id)
        ).rowcount
        out["wearable_sync_states_deleted"] = session.execute(
            delete(WearableSyncState).where(WearableSyncState.athlete_id == athlete_id)
        ).rowcount
        owner_ids = list(session.scalars(
            select(AthleteAccess.user_id).where(AthleteAccess.athlete_id == athlete_id)
        ))
        for owner_id in owner_ids:
            owner = session.get(User, owner_id)
            if owner and owner.role == "athlete":
                session.execute(delete(AuthSession).where(AuthSession.user_id == owner_id))
                session.execute(delete(AthleteAccess).where(AthleteAccess.user_id == owner_id))
                session.delete(owner)
        session.execute(delete(AthleteAccess).where(AthleteAccess.athlete_id == athlete_id))
        out["athlete_deleted"] = session.execute(delete(Athlete).where(Athlete.id == athlete_id)).rowcount
    session.commit()
    short_term.clear(athlete_id)
    return out
