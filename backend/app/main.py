"""API FastAPI di BioPulse-Agent."""
from __future__ import annotations

import json
import logging
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import Body, Depends, FastAPI, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import delete, exists, func, select

from . import services
from .agent import llm_available
from .auth import (CSRF_COOKIE, Principal, accessible_athletes, authorize_athlete, clear_cookies,
                   check_demo_chat_rate_limit, current_principal, login as authenticate,
                   require_clinician, require_csrf,
                   start_demo as create_demo_session,
                   register_athlete as create_athlete_account, revoke_session)
from .config import get_settings
from .db import (AlertLog, Athlete, AthleteAccess, AuthSession, ConsentEvent, DailyMetric, HitlCase, KnowledgeDoc,
                 MemoryNote, SessionLocal, User, WearableSyncState, init_db)
from .memory import erase, short_term
from .pipeline import run_chat
from .schemas import (AthleteProfileUpdate, AthleteRegistrationRequest, ChatRequest, ConsentUpdate, DecisionIn, LoginRequest, SeedRequest,
                     WearableSyncRequest)
from .simulator import SCENARIOS, generate_series
from .wearable import PROVIDER_ID, fetch_synthetic_records, normalize_synthetic_record
from .whitebox.sanitizer import sanitize_batch

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("biopulse.api")
settings = get_settings()


def purge_expired_data() -> dict[str, int]:
    now = datetime.now(timezone.utc)
    metric_cutoff = (now - timedelta(days=settings.biometric_retention_days)).date()
    clinical_cutoff = now - timedelta(days=settings.clinical_retention_days)
    expired_guest_athletes: list[str] = []
    with SessionLocal.begin() as session:
        active_guest_session = exists(select(AuthSession.token_hash).where(
            AuthSession.user_id == User.id,
            AuthSession.expires_at > now,
            AuthSession.revoked_at.is_(None),
        ))
        expired_guest_ids = list(session.scalars(
            select(User.id).where(User.is_demo_guest.is_(True), ~active_guest_session)
        ))
        if expired_guest_ids:
            expired_guest_athletes = list(session.scalars(
                select(AthleteAccess.athlete_id).where(AthleteAccess.user_id.in_(expired_guest_ids))
            ))
            if expired_guest_athletes:
                session.execute(delete(DailyMetric).where(DailyMetric.athlete_id.in_(expired_guest_athletes)))
                session.execute(delete(WearableSyncState).where(
                    WearableSyncState.athlete_id.in_(expired_guest_athletes)
                ))
                session.execute(delete(MemoryNote).where(MemoryNote.athlete_id.in_(expired_guest_athletes)))
                session.execute(delete(HitlCase).where(HitlCase.athlete_id.in_(expired_guest_athletes)))
                session.execute(delete(AlertLog).where(AlertLog.athlete_id.in_(expired_guest_athletes)))
                session.execute(delete(ConsentEvent).where(ConsentEvent.athlete_id.in_(expired_guest_athletes)))
            session.execute(delete(AuthSession).where(AuthSession.user_id.in_(expired_guest_ids)))
            session.execute(delete(AthleteAccess).where(AthleteAccess.user_id.in_(expired_guest_ids)))
            session.execute(delete(User).where(User.id.in_(expired_guest_ids)))
            if expired_guest_athletes:
                session.execute(delete(Athlete).where(Athlete.id.in_(expired_guest_athletes)))
        counts = {
            "metrics": session.execute(delete(DailyMetric).where(DailyMetric.day < metric_cutoff)).rowcount or 0,
            "memory": session.execute(delete(MemoryNote).where(
                MemoryNote.created_at < now - timedelta(days=settings.biometric_retention_days)
            )).rowcount or 0,
            "cases": session.execute(delete(HitlCase).where(
                HitlCase.status != "pending", HitlCase.reviewed_at.is_not(None),
                HitlCase.reviewed_at < clinical_cutoff,
            )).rowcount or 0,
            "alerts": session.execute(delete(AlertLog).where(AlertLog.created_at < clinical_cutoff)).rowcount or 0,
            "consent_history": session.execute(delete(ConsentEvent).where(
                ConsentEvent.changed_at < clinical_cutoff,
                ConsentEvent.id.not_in(
                    select(func.max(ConsentEvent.id)).group_by(ConsentEvent.athlete_id,
                                                              ConsentEvent.consent_type)
                ),
            )).rowcount or 0,
            "sessions": session.execute(delete(AuthSession).where(
                (AuthSession.expires_at < now) | (AuthSession.revoked_at.is_not(None))
            )).rowcount or 0,
            "demo_guests": len(expired_guest_ids),
        }
    for athlete_id in expired_guest_athletes:
        short_term.clear(athlete_id)
    return counts


async def _retention_worker() -> None:
    while True:
        try:
            deleted = purge_expired_data()
            if any(deleted.values()):
                log.info("Pulizia retention completata: %s", deleted)
        except Exception:
            log.exception("Pulizia retention fallita")
        await asyncio.sleep(5 * 60 if settings.public_demo_enabled else 24 * 60 * 60)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.validate_security_settings()
    init_db()
    with SessionLocal() as s:
        n = services.seed_knowledge(s)
    log.info("DB pronto (%s). Documenti di conoscenza aggiunti/aggiornati: %d. LLM: %s",
             "postgres" if settings.is_postgres else "sqlite", n, "attivo" if llm_available() else "modalità deterministica")
    purge_expired_data()
    worker = asyncio.create_task(_retention_worker())
    try:
        yield
    finally:
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass


app = FastAPI(title="BioPulse-Agent API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
                   allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                   allow_headers=["Content-Type", "X-CSRF-Token"], allow_credentials=True)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"] = "no-store"
    if settings.cookie_secure:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# --- Gestione errori: mai stack trace verso il client (T1) -------------------
@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError):
    fields = [{"campo": ".".join(str(x) for x in e.get("loc", [])), "problema": e.get("msg")} for e in exc.errors()]
    return JSONResponse(status_code=422, content=jsonable_encoder(
        {"detail": "Richiesta non valida: controlla i campi indicati.", "fields": fields}))


@app.exception_handler(Exception)
async def generic_handler(_: Request, exc: Exception):
    log.exception("Errore non gestito")
    return JSONResponse(status_code=500, content={"detail": "Errore interno gestito. Riprova tra poco."})


# --- Salute / info -----------------------------------------------------------
@app.get("/api/health")
def health():
    with SessionLocal() as s:
        n_docs = s.scalar(select(func.count()).select_from(KnowledgeDoc))
    return {"status": "ok", "llm": llm_available(), "llm_model": settings.groq_model,
            "memory_backend": short_term.backend, "database": "postgresql+pgvector" if settings.is_postgres else "sqlite",
            "knowledge_docs": n_docs, "scenarios": SCENARIOS, "demo_mode": settings.demo_mode}


# --- Autenticazione ----------------------------------------------------------
@app.post("/api/auth/login")
def auth_login(body: LoginRequest, request: Request, response: Response):
    return authenticate(request, response, body.email, body.password)


@app.post("/api/auth/demo")
def auth_demo(request: Request, response: Response):
    return create_demo_session(request, response)


@app.get("/api/auth/options")
def auth_options():
    return {"self_registration": (
        settings.allow_self_registration and settings.demo_mode and settings.app_env == "development"
    ), "public_demo": settings.public_demo_enabled}


@app.post("/api/auth/register", status_code=201)
def auth_register(body: AthleteRegistrationRequest, request: Request, response: Response):
    return create_athlete_account(request, response, body.email, body.password, body.name, body.profile)


@app.get("/api/auth/session")
def auth_session(request: Request, principal: Principal = Depends(current_principal)):
    with SessionLocal() as session:
        ids = accessible_athletes(session, principal)
        query = select(Athlete)
        if ids is not None:
            query = query.where(Athlete.id.in_(ids))
        athletes = session.scalars(query).all()
    return {
        "user": {"id": principal.user_id, "email": principal.email, "role": principal.role,
                 "demo_guest": principal.demo_guest},
        "athletes": [{"id": a.id, "name": a.name, "profile": a.profile} for a in athletes],
        "csrf_token": request.cookies.get(CSRF_COOKIE),
        "demo_mode": settings.demo_mode,
    }


@app.post("/api/auth/logout")
def auth_logout(request: Request, response: Response, _: Principal = Depends(require_csrf)):
    revoke_session(request)
    clear_cookies(response)
    return {"ok": True}


# --- Atleti e dati -----------------------------------------------------------
@app.get("/api/athletes")
def list_athletes(principal: Principal = Depends(current_principal)):
    with SessionLocal() as s:
        ids = accessible_athletes(s, principal)
        query = select(Athlete)
        if ids is not None:
            query = query.where(Athlete.id.in_(ids))
        return [{"id": a.id, "name": a.name, "profile": a.profile} for a in s.scalars(query)]


@app.put("/api/athletes/{athlete_id}/profile")
def update_athlete_profile(athlete_id: str, body: AthleteProfileUpdate,
                           principal: Principal = Depends(require_csrf)):
    if principal.role != "athlete":
        raise HTTPException(403, "Solo l'atleta può modificare il proprio profilo.")
    if body.name is None and body.profile is None:
        raise HTTPException(422, "Indica almeno un campo del profilo da aggiornare.")
    with SessionLocal.begin() as s:
        athlete = s.get(Athlete, athlete_id)
        if athlete is None:
            raise HTTPException(404, "Atleta non trovato.")
        authorize_athlete(s, principal, athlete_id)
        if body.name is not None:
            name = body.name.strip()
            if not name:
                raise HTTPException(422, "Il nome visualizzato non può essere vuoto.")
            athlete.name = name
        if body.profile is not None:
            athlete.profile = body.profile
        return {"id": athlete.id, "name": athlete.name, "profile": athlete.profile}


@app.post("/api/demo/seed")
def seed_demo(req: SeedRequest, principal: Principal = Depends(require_csrf)):
    """Crea (o ricrea) un atleta con 42 giorni di dati simulati nello scenario scelto."""
    if not (settings.demo_mode or (settings.public_demo_enabled and principal.demo_guest)):
        raise HTTPException(404, "Funzione demo non disponibile.")
    if principal.role != "athlete":
        raise HTTPException(403, "Solo l'atleta può caricare dati demo nel proprio profilo.")
    with SessionLocal() as s:
        a = s.get(Athlete, req.athlete_id)
        if a is None and settings.app_env == "test" and settings.auth_disabled:
            a = services.ensure_athlete(s, req.athlete_id, req.name, req.profile,
                                        req.consent_data if req.consent_data is not None else True,
                                        req.consent_alerts if req.consent_alerts is not None else True)
        authorize_athlete(s, principal, req.athlete_id)
        if a is None:
            raise HTTPException(404, "Atleta non trovato.")
        if req.consent_data is not None or req.consent_alerts is not None:
            if not (settings.app_env == "test" and settings.auth_disabled):
                raise HTTPException(422, "I consensi si modificano solo dall'endpoint dedicato.")
        if not a.consent_data:
            raise HTTPException(403, "Consenso al trattamento dei dati mancante.")
        services.clear_metrics(s, req.athlete_id)
        ok, _ = sanitize_batch(generate_series(req.scenario, seed=req.seed))
        services.upsert_metrics(s, req.athlete_id, ok)
        return services.dashboard(s, req.athlete_id)


@app.put("/api/athletes/{athlete_id}/consent")
def update_consent(athlete_id: str, body: ConsentUpdate, principal: Principal = Depends(require_csrf)):
    with SessionLocal() as s:
        a = s.get(Athlete, athlete_id)
        if a is None:
            raise HTTPException(404, "Atleta non trovato.")
        authorize_athlete(s, principal, athlete_id)
        if body.consent_data is None and body.consent_alerts is None:
            raise HTTPException(422, "Indica almeno un consenso da aggiornare.")
        if principal.demo_guest and body.consent_alerts is True:
            raise HTTPException(403, "Gli avvisi a professionisti sono disattivati nella beta pubblica.")
        if principal.demo_guest and body.consent_data is True and not settings.public_demo_enabled:
            raise HTTPException(404, "La beta pubblica non è disponibile.")
        changes = []
        if principal.role != "athlete":
            raise HTTPException(403, "Solo l'atleta può modificare i propri consensi.")
        if body.consent_data is not None:
            if a.consent_data != body.consent_data:
                changes.append(("data_processing", body.consent_data))
            a.consent_data = body.consent_data
        if body.consent_alerts is not None:
            if a.consent_alerts != body.consent_alerts:
                changes.append(("clinician_alerts", body.consent_alerts))
            a.consent_alerts = body.consent_alerts
        for kind, granted in changes:
            s.add(ConsentEvent(athlete_id=athlete_id, actor_user_id=principal.user_id,
                               consent_type=kind, version=settings.consent_version, granted=granted))
        if body.consent_data is False:
            s.execute(delete(MemoryNote).where(MemoryNote.athlete_id == athlete_id))
        s.commit()
        if body.consent_data is False:
            short_term.clear(athlete_id)
        return {"consent_data": a.consent_data, "consent_alerts": a.consent_alerts,
                "consent_version": settings.consent_version}


@app.post("/api/athletes/{athlete_id}/telemetry")
def ingest(athlete_id: str, payload: Any = Body(default=None),
           principal: Principal = Depends(require_csrf)):
    """Ingestione telemetria. Accetta una lista di record o {"records": [...]}. Mai 500 su dati sporchi (T1, T2)."""
    records = payload.get("records") if isinstance(payload, dict) else payload
    with SessionLocal() as s:
        a = s.get(Athlete, athlete_id)
        if a is None:
            raise HTTPException(404, "Atleta non trovato.")
        authorize_athlete(s, principal, athlete_id)
        if principal.role != "athlete":
            raise HTTPException(403, "Solo l'atleta può caricare la propria telemetria.")
        if not a.consent_data:
            raise HTTPException(403, "Consenso al trattamento dei dati mancante.")
        ok, bad = sanitize_batch(records)
        n = services.upsert_metrics(s, athlete_id, ok) if ok else 0
    msg = ("Payload vuoto: nessun dato da elaborare." if records in (None, [], {}) else
           f"{n} record accettati, {len(bad)} scartati." + (" Ricalibra o ricollega il sensore." if bad else ""))
    return {"accepted": n, "rejected": bad, "message": msg}


@app.post("/api/athletes/{athlete_id}/wearable/sync")
def sync_wearable(athlete_id: str, body: WearableSyncRequest,
                  principal: Principal = Depends(require_csrf)):
    """Sincronizza il provider wearable sintetico; i dati sono fittizi e solo per la demo."""
    if not settings.demo_mode:
        raise HTTPException(404, "La fonte wearable sintetica è disponibile solo in modalità demo.")
    if principal.role != "athlete":
        raise HTTPException(403, "Solo l'atleta può sincronizzare il proprio wearable.")

    sync_error = False
    result: dict[str, Any] = {}
    with SessionLocal.begin() as session:
        athlete = session.get(Athlete, athlete_id)
        if athlete is None:
            raise HTTPException(404, "Atleta non trovato.")
        authorize_athlete(session, principal, athlete_id)
        if not athlete.consent_data:
            raise HTTPException(403, "Consenso al trattamento dei dati mancante.")

        state = session.scalar(
            select(WearableSyncState)
            .where(WearableSyncState.athlete_id == athlete_id,
                   WearableSyncState.provider == PROVIDER_ID)
            .with_for_update()
        )
        if state is None:
            state = WearableSyncState(athlete_id=athlete_id, provider=PROVIDER_ID)
            session.add(state)
            session.flush()

        records = [
            normalize_synthetic_record(record)
            for record in fetch_synthetic_records(body.scenario, body.seed, state.cursor_day)
        ]
        clean, rejected = sanitize_batch(records)
        now = datetime.now(timezone.utc)
        if rejected:
            state.status = "failed"
            state.last_attempt_at = now
            state.records_received = len(records)
            state.records_accepted = 0
            state.rejected_count = len(rejected)
            state.last_error = "La fonte sintetica ha restituito record non validi."
            sync_error = True
        else:
            services.upsert_metrics(session, athlete_id, clean, commit=False)
            latest_day = max((record.day for record in clean), default=state.cursor_day)
            state.cursor_day = latest_day
            state.status = "success"
            state.last_attempt_at = now
            state.last_success_at = now
            state.records_received = len(records)
            state.records_accepted = len(clean)
            state.rejected_count = 0
            state.last_error = None
            result = {
                "provider": PROVIDER_ID,
                "status": state.status,
                "records_received": state.records_received,
                "records_accepted": state.records_accepted,
                "rejected_count": state.rejected_count,
                "cursor_day": state.cursor_day.isoformat() if state.cursor_day else None,
                "last_success_at": state.last_success_at.isoformat(),
                "synthetic": True,
            }
    if sync_error:
        raise HTTPException(502, "La sincronizzazione wearable non è riuscita: record non validi.")
    return result


@app.get("/api/athletes/{athlete_id}/dashboard")
def get_dashboard(athlete_id: str, principal: Principal = Depends(current_principal)):
    with SessionLocal() as s:
        authorize_athlete(s, principal, athlete_id)
        athlete = s.get(Athlete, athlete_id)
        if athlete is None:
            raise HTTPException(404, "Atleta non trovato.")
        try:
            return services.dashboard(s, athlete_id)
        except LookupError:
            raise HTTPException(404, "Atleta non trovato. Carica i dati demo.")


@app.delete("/api/athletes/{athlete_id}/data")
def delete_data(athlete_id: str, scope: str = "memory",
                principal: Principal = Depends(require_csrf)):
    """Diritto alla cancellazione (GDPR art. 17). scope=memory cancella la memoria dell'agente; scope=all tutto."""
    if scope not in ("memory", "all"):
        raise HTTPException(422, "scope deve essere 'memory' o 'all'.")
    with SessionLocal() as s:
        authorize_athlete(s, principal, athlete_id)
        if principal.role != "athlete":
            raise HTTPException(403, "Solo l'atleta può cancellare i propri dati.")
        return erase(s, athlete_id, scope)


# --- Chat (SSE) --------------------------------------------------------------
@app.post("/api/chat")
def chat(req: ChatRequest, principal: Principal = Depends(require_csrf)):
    if req.simulate_failure and not (
        settings.demo_mode or (settings.public_demo_enabled and principal.demo_guest)
    ):
        raise HTTPException(422, "La simulazione dei guasti è disponibile solo in demo.")
    check_demo_chat_rate_limit(principal)
    with SessionLocal() as s:
        ids = accessible_athletes(s, principal)
        athlete_id = req.athlete_id
        if not athlete_id:
            if ids is None:
                ids = list(s.scalars(select(Athlete.id)))
            if len(ids) == 1:
                athlete_id = ids[0]
        if not athlete_id:
            raise HTTPException(422, "Seleziona un atleta assegnato al tuo account.")
        authorize_athlete(s, principal, athlete_id)
        if principal.role != "athlete":
            raise HTTPException(403, "La chat biometrica è disponibile solo per l'account dell'atleta.")

    def gen():
        for ev in run_chat(athlete_id, req.message, req.simulate_failure):
            yield f"data: {json.dumps(ev, ensure_ascii=False, default=str)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/athletes/{athlete_id}/validated")
def validated(athlete_id: str, principal: Principal = Depends(current_principal)):
    """Raccomandazioni già valutate dal professionista, visibili all'atleta."""
    with SessionLocal() as s:
        authorize_athlete(s, principal, athlete_id)
        if principal.role != "athlete":
            raise HTTPException(403, "Solo l'atleta può consultare il proprio riepilogo clinico.")
        return services.validated_for(s, athlete_id)


# --- Pannello HITL (riservato) -----------------------------------------------
@app.get("/api/hitl/cases")
def hitl_cases(status: Optional[str] = None, principal: Principal = Depends(require_clinician)):
    with SessionLocal() as s:
        ids = accessible_athletes(s, principal)
        return services.list_cases(s, status, ids)


@app.post("/api/hitl/cases/{case_id}/decision")
def hitl_decision(case_id: int, body: DecisionIn, principal: Principal = Depends(require_csrf),
                  _: Principal = Depends(require_clinician)):
    with SessionLocal() as s:
        case = s.get(HitlCase, case_id)
        if case is None:
            raise HTTPException(404, "Caso non trovato.")
        authorize_athlete(s, principal, case.athlete_id)
        try:
            c = services.decide_case(s, case_id, body.decision, principal.email, body.note, body.final_text)
        except LookupError:
            raise HTTPException(404, "Caso non trovato.")
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        return services.case_to_dict(c)


@app.get("/api/hitl/alerts")
def hitl_alerts(principal: Principal = Depends(require_clinician)):
    with SessionLocal() as s:
        return services.list_alerts(s, accessible_athletes(s, principal))
