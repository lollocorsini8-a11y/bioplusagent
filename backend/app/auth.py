"""Autenticazione locale a sessioni opache, cookie HttpOnly e controllo CSRF."""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import re
import secrets
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import redis
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .config import get_settings
from .db import Athlete, AthleteAccess, AuthSession, SessionLocal, User

SESSION_COOKIE = "biopulse_session"
CSRF_COOKIE = "biopulse_csrf"
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**14, 8, 1
_LOGIN_LIMIT, _LOGIN_WINDOW_S = 10, 15 * 60
_DEMO_GUEST_CREATE_LIMIT, _DEMO_GUEST_CREATE_WINDOW_S = 10, 60 * 60
_DEMO_CHAT_LIMIT, _DEMO_CHAT_WINDOW_S = 10, 60 * 60
_LOGIN_ATTEMPTS: dict[str, tuple[float, int]] = {}
_LOGIN_ATTEMPTS_LOCK = threading.Lock()
_LOGIN_REDIS: Optional[redis.Redis] = None
log = logging.getLogger("biopulse.auth")


@dataclass(frozen=True)
class Principal:
    user_id: str
    email: str
    role: str
    csrf_hash: Optional[str] = None
    demo_guest: bool = False


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("La password deve contenere almeno 12 caratteri.")
    salt = secrets.token_bytes(16)
    key = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R,
                         p=_SCRYPT_P, dklen=32, maxmem=64 * 1024 * 1024)
    return "scrypt${}${}${}${}${}".format(
        _SCRYPT_N, _SCRYPT_R, _SCRYPT_P,
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(key).decode("ascii"),
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt_b64, key_b64 = encoded.split("$")
        if algorithm != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
        expected = base64.urlsafe_b64decode(key_b64.encode("ascii"))
        actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=int(n), r=int(r),
                                p=int(p), dklen=len(expected), maxmem=64 * 1024 * 1024)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError, UnicodeError):
        return False


_DUMMY_PASSWORD_HASH = hash_password("BioPulse-dummy-password")


def validate_email(email: str) -> str:
    normalized = email.strip().casefold()
    if len(normalized) > 254 or not _EMAIL.fullmatch(normalized):
        raise ValueError("Indirizzo email non valido.")
    return normalized


def _validate_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin:
        allowed = {o.strip().rstrip("/") for o in get_settings().cors_origins.split(",") if o.strip()}
        if origin.rstrip("/") not in allowed:
            raise HTTPException(403, "Origine della richiesta non autorizzata.")


def _local_login_attempt(ip_key: str, window_s: int = _LOGIN_WINDOW_S) -> int:
    now = time.monotonic()
    with _LOGIN_ATTEMPTS_LOCK:
        for key, (started, _) in list(_LOGIN_ATTEMPTS.items()):
            if now - started >= window_s:
                del _LOGIN_ATTEMPTS[key]
        started, count = _LOGIN_ATTEMPTS.get(ip_key, (now, 0))
        count = count + 1 if now - started < window_s else 1
        _LOGIN_ATTEMPTS[ip_key] = (started if count > 1 else now, count)
        if len(_LOGIN_ATTEMPTS) > 4096:
            del _LOGIN_ATTEMPTS[next(iter(_LOGIN_ATTEMPTS))]
        return count


def _check_login_rate_limit(request: Request) -> None:
    _check_rate_limit(request, "auth:login", _LOGIN_LIMIT, _LOGIN_WINDOW_S)


def _check_rate_limit(request: Optional[Request], namespace: str, limit: int, window_s: int,
                      subject: Optional[str] = None) -> None:
    global _LOGIN_REDIS
    address = subject or (request.client.host if request and request.client else "unknown")
    key_digest = hashlib.sha256(address.encode("utf-8")).hexdigest()
    key = f"{namespace}:{key_digest}"
    settings = get_settings()
    count: int
    if settings.redis_url:
        if _LOGIN_REDIS is None:
            _LOGIN_REDIS = redis.Redis.from_url(
                settings.redis_url, socket_connect_timeout=1, socket_timeout=1
            )
        try:
            count = int(_LOGIN_REDIS.eval(
                "local n=redis.call('INCR',KEYS[1]); "
                "if n==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end; return n",
                1, key, window_s,
            ))
        except redis.RedisError as exc:
            if settings.app_env == "production":
                log.exception("Redis non disponibile per il limite di frequenza %s.", namespace)
                raise HTTPException(503, "Servizio temporaneamente non disponibile.") from exc
            log.warning("Redis non disponibile per %s; uso il limite locale.", namespace)
            count = _local_login_attempt(key, window_s)
    else:
        count = _local_login_attempt(key, window_s)
    if count > limit:
        raise HTTPException(429, "Hai raggiunto il limite temporaneo. Riprova più tardi.",
                            headers={"Retry-After": str(window_s)})


def _check_demo_guest_creation_rate_limit(request: Request) -> None:
    _check_rate_limit(request, "demo:create:ip", _DEMO_GUEST_CREATE_LIMIT,
                      _DEMO_GUEST_CREATE_WINDOW_S)


def check_demo_chat_rate_limit(principal: Principal) -> None:
    if principal.demo_guest:
        _check_rate_limit(
            None, "demo:chat:user", _DEMO_CHAT_LIMIT, _DEMO_CHAT_WINDOW_S, principal.user_id,
        )


def login(request: Request, response: Response, email: str, password: str) -> dict:
    _validate_origin(request)
    _check_login_rate_limit(request)
    try:
        normalized = validate_email(email)
    except ValueError:
        normalized = ""
    with SessionLocal() as session:
        user = session.scalar(select(User).where(User.email == normalized, User.active.is_(True)))
        verified = verify_password(password, user.password_hash if user else _DUMMY_PASSWORD_HASH)
        if user is None or not verified:
            raise HTTPException(401, "Email o password non corretti.")
        now = datetime.now(timezone.utc)
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        auth_session = AuthSession(
            token_hash=_digest(token), csrf_hash=_digest(csrf), user_id=user.id,
            expires_at=now + timedelta(hours=get_settings().session_hours),
        )
        user.last_login_at = now
        session.add(auth_session)
        session.commit()
        _set_cookies(response, token, csrf)
        return {"user": {"id": user.id, "email": user.email, "role": user.role,
                         "demo_guest": user.is_demo_guest}, "csrf_token": csrf}


def start_demo(request: Request, response: Response) -> dict:
    settings = get_settings()
    if not settings.public_demo_enabled:
        raise HTTPException(404, "La beta pubblica non è disponibile.")
    if settings.app_env == "production" and not request.headers.get("origin"):
        raise HTTPException(403, "Origine della richiesta non autorizzata.")
    _validate_origin(request)
    _check_demo_guest_creation_rate_limit(request)
    user_id, athlete_id = str(uuid.uuid4()), str(uuid.uuid4())
    email = f"demo-{uuid.uuid4().hex}@example.invalid"
    user = User(id=user_id, email=email, password_hash="",
                role="athlete", is_demo_guest=True)
    athlete = Athlete(id=athlete_id, name="Atleta demo", profile="standard",
                      consent_data=False, consent_alerts=False)
    with SessionLocal.begin() as session:
        session.add_all((user, athlete))
        session.flush()
        session.add(AthleteAccess(user_id=user_id, athlete_id=athlete_id))
        token, csrf = create_session_for_user(session, user, hours=2)
    _set_cookies(response, token, csrf, session_hours=2)
    return {"user": {"id": user_id, "email": email, "role": "athlete", "demo_guest": True},
            "csrf_token": csrf}


def register_athlete(request: Request, response: Response, email: str, password: str,
                     name: str, profile: str) -> dict:
    settings = get_settings()
    if not (settings.allow_self_registration and settings.demo_mode and settings.app_env == "development"):
        raise HTTPException(404, "Registrazione non disponibile.")
    _validate_origin(request)
    _check_login_rate_limit(request)
    try:
        normalized = validate_email(email)
        password_hash = hash_password(password)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if not name.strip():
        raise HTTPException(422, "Il nome visualizzato non può essere vuoto.")

    user_id, athlete_id = str(uuid.uuid4()), str(uuid.uuid4())
    token = csrf = ""
    try:
        with SessionLocal.begin() as session:
            if session.scalar(select(User.id).where(User.email == normalized)):
                raise HTTPException(409, "Esiste già un account con questa email.")
            user = User(id=user_id, email=normalized, password_hash=password_hash, role="athlete")
            athlete = Athlete(id=athlete_id, name=name.strip(), profile=profile,
                              consent_data=False, consent_alerts=False)
            session.add_all((user, athlete))
            session.flush()
            session.add(AthleteAccess(user_id=user_id, athlete_id=athlete_id))
            token, csrf = create_session_for_user(session, user)
    except IntegrityError as exc:
        log.info("Registrazione duplicata rifiutata per %s", normalized)
        raise HTTPException(409, "Esiste già un account con questa email.") from exc

    _set_cookies(response, token, csrf)
    return {"user": {"id": user_id, "email": normalized, "role": "athlete",
                     "demo_guest": False}, "csrf_token": csrf}


def _set_cookies(response: Response, token: str, csrf: str,
                 session_hours: Optional[int] = None) -> None:
    settings = get_settings()
    common = {"max_age": (session_hours or settings.session_hours) * 3600,
              "path": "/api", "secure": settings.cookie_secure,
              "samesite": "strict"}
    response.set_cookie(SESSION_COOKIE, token, httponly=True, **common)
    response.set_cookie(CSRF_COOKIE, csrf, httponly=False, **common)


def clear_cookies(response: Response) -> None:
    for name in (SESSION_COOKIE, CSRF_COOKIE):
        response.delete_cookie(name, path="/api", secure=get_settings().cookie_secure, samesite="strict")


def current_principal(request: Request) -> Principal:
    settings = get_settings()
    if settings.app_env == "test" and settings.auth_disabled:
        return Principal("test-user", "test@example.invalid", "athlete")
    _validate_origin(request)
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(401, "Autenticazione richiesta.")
    with SessionLocal() as session:
        row = session.execute(
            select(AuthSession, User)
            .join(User, AuthSession.user_id == User.id)
            .where(AuthSession.token_hash == _digest(token), AuthSession.revoked_at.is_(None),
                   AuthSession.expires_at > datetime.now(timezone.utc), User.active.is_(True))
        ).first()
        if row is None:
            raise HTTPException(401, "Sessione non valida o scaduta.")
        auth_session, user = row
        return Principal(user.id, user.email, user.role, auth_session.csrf_hash, user.is_demo_guest)


def require_csrf(request: Request, principal: Principal = Depends(current_principal)) -> Principal:
    settings = get_settings()
    if settings.app_env == "test" and settings.auth_disabled:
        return principal
    cookie, header = request.cookies.get(CSRF_COOKIE), request.headers.get("x-csrf-token")
    if not cookie or not header or not hmac.compare_digest(cookie, header):
        raise HTTPException(403, "Verifica CSRF non superata.")
    if principal.csrf_hash is None or not hmac.compare_digest(_digest(header), principal.csrf_hash):
        raise HTTPException(403, "Token CSRF non valido.")
    return principal


def require_clinician(
    request: Request,
    principal: Principal = Depends(current_principal),
) -> Principal:
    settings = get_settings()
    if settings.app_env == "test" and settings.auth_disabled:
        key = request.headers.get("x-clinician-key", "")
        if not hmac.compare_digest(key.encode(), b"demo-clinician"):
            raise HTTPException(401, "Area riservata a medici e preparatori atletici.")
        return principal
    if principal.role != "clinician":
        raise HTTPException(403, "Accesso riservato ai professionisti autorizzati.")
    return principal


def authorize_athlete(session, principal: Principal, athlete_id: str) -> None:
    settings = get_settings()
    if settings.app_env == "test" and settings.auth_disabled:
        return
    if principal.role not in ("athlete", "clinician"):
        raise HTTPException(403, "Ruolo non autorizzato ad accedere ai dati dell'atleta.")
    allowed = session.scalar(
        select(AthleteAccess.id).where(AthleteAccess.user_id == principal.user_id,
                                       AthleteAccess.athlete_id == athlete_id)
    )
    if allowed is None:
        raise HTTPException(404, "Atleta non trovato o non assegnato al tuo account.")


def accessible_athletes(session, principal: Principal) -> Optional[list[str]]:
    settings = get_settings()
    if settings.app_env == "test" and settings.auth_disabled:
        return None
    if principal.role not in ("athlete", "clinician"):
        return []
    return list(session.scalars(
        select(AthleteAccess.athlete_id).where(AthleteAccess.user_id == principal.user_id)
    ))


def create_session_for_user(session, user: User, hours: Optional[int] = None) -> tuple[str, str]:
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    session.add(AuthSession(
        token_hash=_digest(token), csrf_hash=_digest(csrf), user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=hours or get_settings().session_hours),
    ))
    return token, csrf


def revoke_session(request: Request) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return
    with SessionLocal() as session:
        auth_session = session.get(AuthSession, _digest(token))
        if auth_session and auth_session.revoked_at is None:
            auth_session.revoked_at = datetime.now(timezone.utc)
            session.commit()
