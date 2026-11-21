"""Logica applicativa condivisa da API, tool dell'agente e pipeline."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .db import Athlete, DailyMetric, HitlCase, KnowledgeDoc, AlertLog
from .embeddings import embed
from .whitebox.metrics import StrainReport, compute_strain_report
from .whitebox.sanitizer import CleanRecord

KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"
METRIC_FIELDS = ["day", "rmssd_ms", "resting_hr", "hr_max", "sleep_hours", "sleep_efficiency", "spo2",
                 "skin_temp_c", "rpe", "duration_min", "doms", "load"]


def ensure_athlete(session: Session, athlete_id: str, name: Optional[str] = None, profile: str = "standard",
                   consent_data: bool = True, consent_alerts: bool = False) -> Athlete:
    a = session.get(Athlete, athlete_id)
    if a is None:
        a = Athlete(id=athlete_id, name=name or athlete_id, profile=profile,
                    consent_data=consent_data, consent_alerts=consent_alerts)
        session.add(a)
        session.commit()
    return a


def upsert_metrics(session: Session, athlete_id: str, records: list[CleanRecord],
                   commit: bool = True) -> int:
    for rec in records:
        row = session.scalar(select(DailyMetric).where(DailyMetric.athlete_id == athlete_id,
                                                       DailyMetric.day == rec.day))
        if row is None:
            row = DailyMetric(athlete_id=athlete_id, day=rec.day)
            session.add(row)
        for f in METRIC_FIELDS[1:]:
            setattr(row, f, getattr(rec, f))
    if commit:
        session.commit()
    return len(records)


def clear_metrics(session: Session, athlete_id: str) -> None:
    session.execute(delete(DailyMetric).where(DailyMetric.athlete_id == athlete_id))
    session.commit()


def get_series(session: Session, athlete_id: str, days: int = 35) -> list[dict]:
    last = session.scalar(select(DailyMetric.day).where(DailyMetric.athlete_id == athlete_id)
                          .order_by(DailyMetric.day.desc()).limit(1))
    if last is None:
        return []
    start = last - timedelta(days=days - 1)
    rows = session.scalars(select(DailyMetric).where(DailyMetric.athlete_id == athlete_id,
                                                     DailyMetric.day >= start)
                           .order_by(DailyMetric.day)).all()
    return [{f: getattr(r, f) for f in METRIC_FIELDS} for r in rows]


def compute_report(session: Session, athlete_id: str) -> StrainReport:
    return compute_strain_report(get_series(session, athlete_id, 35))


def dashboard(session: Session, athlete_id: str) -> dict:
    a = session.get(Athlete, athlete_id)
    if a is None:
        raise LookupError(athlete_id)
    if not a.consent_data:
        return {
            "athlete": {"id": a.id, "name": a.name, "profile": a.profile,
                        "consent_data": a.consent_data, "consent_alerts": a.consent_alerts},
            "report": compute_strain_report([]).to_dict(),
            "series": [],
        }
    series = get_series(session, athlete_id, 28)
    report = compute_strain_report(get_series(session, athlete_id, 35))
    return {
        "athlete": {"id": a.id, "name": a.name, "profile": a.profile,
                    "consent_data": a.consent_data, "consent_alerts": a.consent_alerts},
        "report": report.to_dict(),
        "series": [{**s, "day": s["day"].isoformat()} for s in series],
    }


# --- Knowledge base ----------------------------------------------------------
def seed_knowledge(session: Session) -> int:
    changed = 0
    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        head, _, body = raw.partition("\n\n")
        meta = dict(line.split(":", 1) for line in head.splitlines() if ":" in line)
        slug = path.stem
        doc = session.scalar(select(KnowledgeDoc).where(KnowledgeDoc.slug == slug))
        title, source = meta.get("title", slug).strip(), meta.get("source", "").strip()
        text = body.strip()
        embedding = embed(f"{title}. {text}")
        if doc is None:
            doc = KnowledgeDoc(slug=slug, title=title, source=source, text=text, embedding=embedding)
            session.add(doc)
            changed += 1
        elif (doc.title, doc.source, doc.text, doc.embedding) != (title, source, text, embedding):
            doc.title, doc.source, doc.text, doc.embedding = title, source, text, embedding
            changed += 1
    session.commit()
    return changed


# --- HITL --------------------------------------------------------------------
def create_case(session: Session, athlete_id: str, trigger: str, report: dict, draft_text: str) -> HitlCase:
    case = HitlCase(athlete_id=athlete_id, trigger=trigger, level=report.get("level", "unknown"),
                    report=report, draft_text=draft_text)
    session.add(case)
    session.commit()
    return case


def case_to_dict(c: HitlCase, athlete_name: Optional[str] = None) -> dict:
    return {"id": c.id, "athlete_id": c.athlete_id, "athlete_name": athlete_name, "status": c.status,
            "trigger": c.trigger, "level": c.level, "report": c.report, "draft_text": c.draft_text,
            "final_text": c.final_text, "reviewer": c.reviewer, "reviewer_note": c.reviewer_note,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "reviewed_at": c.reviewed_at.isoformat() if c.reviewed_at else None}


def list_cases(session: Session, status: Optional[str] = None,
               athlete_ids: Optional[list[str]] = None) -> list[dict]:
    q = select(HitlCase).order_by(HitlCase.created_at.desc())
    if athlete_ids is not None:
        q = q.where(HitlCase.athlete_id.in_(athlete_ids))
    if status:
        q = q.where(HitlCase.status == status)
    out = []
    for c in session.scalars(q).all():
        a = session.get(Athlete, c.athlete_id)
        out.append(case_to_dict(c, a.name if a else None))
    return out


def decide_case(session: Session, case_id: int, decision: str, reviewer: str,
                note: Optional[str] = None, final_text: Optional[str] = None) -> HitlCase:
    c = session.get(HitlCase, case_id)
    if c is None:
        raise LookupError(case_id)
    if c.status != "pending":
        raise ValueError("Caso gia' valutato.")
    if decision == "approve":
        c.status, c.final_text = "approved", c.draft_text
    elif decision == "modify":
        if not (final_text or "").strip():
            raise ValueError("Per modificare serve il testo finale.")
        c.status, c.final_text = "modified", final_text.strip()
    elif decision == "reject":
        if not (note or "").strip():
            raise ValueError("Per respingere indica una motivazione.")
        c.status, c.final_text = "rejected", None
    else:
        raise ValueError("Decisione non valida.")
    c.reviewer, c.reviewer_note = reviewer or "professionista", note
    c.reviewed_at = datetime.now(timezone.utc)
    session.commit()
    return c


def validated_for(session: Session, athlete_id: str) -> list[dict]:
    cs = session.scalars(select(HitlCase).where(HitlCase.athlete_id == athlete_id,
                                                HitlCase.status.in_(["approved", "modified", "rejected"]))
                         .order_by(HitlCase.reviewed_at.desc())).all()
    return [case_to_dict(c) for c in cs]


def list_alerts(session: Session, athlete_ids: Optional[list[str]] = None, limit: int = 20) -> list[dict]:
    q = select(AlertLog).order_by(AlertLog.created_at.desc())
    if athlete_ids is not None:
        q = q.where(AlertLog.athlete_id.in_(athlete_ids))
    rows = session.scalars(q.limit(limit)).all()
    return [{"id": r.id, "athlete_id": r.athlete_id, "channel": r.channel, "body": r.body,
             "simulated": r.simulated, "created_at": r.created_at.isoformat()} for r in rows]
