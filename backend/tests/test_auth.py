from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.auth import hash_password
from app.config import get_settings
from app.db import (AlertLog, Athlete, AthleteAccess, AuthSession, ConsentEvent, DailyMetric, HitlCase,
                    MemoryNote, SessionLocal, User, WearableSyncState)
from app.main import app, purge_expired_data

_created_user_ids: list[str] = []
_created_athlete_ids: list[str] = []


@pytest.fixture
def secured_client(monkeypatch):
    from app import auth

    _created_user_ids.clear()
    _created_athlete_ids.clear()
    with auth._LOGIN_ATTEMPTS_LOCK:
        auth._LOGIN_ATTEMPTS.clear()
    monkeypatch.setattr(get_settings(), "auth_disabled", False)
    with TestClient(app) as client:
        yield client
    with auth._LOGIN_ATTEMPTS_LOCK:
        auth._LOGIN_ATTEMPTS.clear()
    with SessionLocal.begin() as session:
        session.execute(delete(WearableSyncState).where(
            WearableSyncState.athlete_id.in_(_created_athlete_ids)
        ))
        session.execute(delete(DailyMetric).where(DailyMetric.athlete_id.in_(_created_athlete_ids)))
        session.execute(delete(ConsentEvent).where(ConsentEvent.athlete_id.in_(_created_athlete_ids)))
        session.execute(delete(AthleteAccess).where(AthleteAccess.user_id.in_(_created_user_ids)))
        session.execute(delete(AuthSession).where(AuthSession.user_id.in_(_created_user_ids)))
        session.execute(delete(User).where(User.id.in_(_created_user_ids)))
        session.execute(delete(Athlete).where(Athlete.id.in_(_created_athlete_ids)))


def create_account(role: str, assigned_ids: list[str]) -> tuple[str, str, str]:
    suffix = uuid.uuid4().hex
    email = f"{role}-{suffix}@example.test"
    password = "test-password-123"
    user_id = str(uuid.uuid4())
    _created_user_ids.append(user_id)
    _created_athlete_ids.extend(assigned_ids)
    with SessionLocal.begin() as session:
        for athlete_id in assigned_ids:
            if session.get(Athlete, athlete_id) is None:
                session.add(Athlete(id=athlete_id, name=athlete_id, consent_data=True))
        user = User(id=user_id, email=email, password_hash=hash_password(password), role=role)
        session.add(user)
        session.flush()
        for athlete_id in assigned_ids:
            session.add(AthleteAccess(user_id=user_id, athlete_id=athlete_id))
    return email, password, user_id


def test_login_csrf_logout_and_expired_session(secured_client):
    client = secured_client
    athlete_id = f"auth-{uuid.uuid4().hex}"
    email, password, user_id = create_account("athlete", [athlete_id])

    assert client.get("/api/auth/session").status_code == 401
    assert client.post("/api/auth/login", json={"email": email, "password": "wrong-password"}).status_code == 401

    login_response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert login_response.status_code == 200
    csrf_token = login_response.json()["csrf_token"]
    assert "httponly" in login_response.headers["set-cookie"].lower()
    assert client.get("/api/athletes/" + athlete_id + "/dashboard").status_code == 200

    assert client.put(f"/api/athletes/{athlete_id}/consent", json={"consent_alerts": True}).status_code == 403
    updated = client.put(
        f"/api/athletes/{athlete_id}/consent",
        json={"consent_alerts": True},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert updated.status_code == 200 and updated.json()["consent_alerts"] is True
    with SessionLocal() as session:
        event = session.query(ConsentEvent).filter_by(athlete_id=athlete_id).one()
        assert event.actor_user_id == user_id and event.consent_type == "clinician_alerts"
        assert event.granted is True and event.version

    with SessionLocal.begin() as session:
        auth_session = session.query(AuthSession).filter_by(user_id=user_id).one()
        auth_session.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    assert client.get("/api/auth/session").status_code == 401

    login_response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert login_response.status_code == 200
    logout_response = client.post(
        "/api/auth/logout",
        json={},
        headers={"X-CSRF-Token": login_response.json()["csrf_token"]},
    )
    assert logout_response.status_code == 200
    assert client.get("/api/auth/session").status_code == 401


def test_registration_crea_solo_atleta_senza_consenso(secured_client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "allow_self_registration", True)
    client = secured_client

    assert client.get("/api/auth/options").json()["self_registration"] is True
    response = client.post("/api/auth/register", json={
        "email": f"new-{uuid.uuid4().hex}@example.test",
        "password": "secure-test-password",
        "name": "Atleta Demo",
    })

    assert response.status_code == 201
    assert "httponly" in response.headers["set-cookie"].lower()
    session_response = client.get("/api/auth/session")
    athlete = session_response.json()["athletes"][0]
    assert session_response.json()["user"]["role"] == "athlete"
    assert athlete["name"] == "Atleta Demo"
    _created_user_ids.append(session_response.json()["user"]["id"])
    _created_athlete_ids.append(athlete["id"])

    dashboard = client.get(f"/api/athletes/{athlete['id']}/dashboard").json()
    assert dashboard["athlete"]["consent_data"] is False
    csrf = session_response.json()["csrf_token"]
    assert client.post("/api/demo/seed", json={"athlete_id": athlete["id"]},
                       headers={"X-CSRF-Token": csrf}).status_code == 403
    assert client.post("/api/auth/register", json={
        "email": session_response.json()["user"]["email"],
        "password": "secure-test-password",
        "name": "Duplicato",
    }).status_code == 409


def test_registration_rifiutata_se_disabilitata(secured_client, monkeypatch):
    monkeypatch.setattr(get_settings(), "app_env", "production")
    monkeypatch.setattr(get_settings(), "allow_self_registration", False)
    assert secured_client.get("/api/auth/options").json()["self_registration"] is False
    response = secured_client.post("/api/auth/register", json={
        "email": "not-allowed@example.test",
        "password": "secure-test-password",
        "name": "Non autorizzato",
    })
    assert response.status_code == 404


def test_public_demo_creates_isolated_guest_and_expires_it(secured_client, monkeypatch):
    from app import auth

    client = secured_client
    settings = get_settings()
    monkeypatch.setattr(settings, "public_demo_enabled", True)
    monkeypatch.setattr(settings, "demo_mode", False)
    monkeypatch.setattr(auth, "_DEMO_CHAT_LIMIT", 1)

    started = client.post("/api/auth/demo")
    assert started.status_code == 200
    session = client.get("/api/auth/session").json()
    user = session["user"]
    athlete = session["athletes"][0]
    assert user["demo_guest"] is True
    assert athlete["name"] == "Atleta demo"
    assert client.get(f"/api/athletes/{athlete['id']}/dashboard").json()["athlete"]["consent_data"] is False
    user_id, athlete_id = user["id"], athlete["id"]
    _created_user_ids.append(user_id)
    _created_athlete_ids.append(athlete_id)

    csrf = session["csrf_token"]
    assert client.post("/api/demo/seed", json={"athlete_id": athlete_id},
                       headers={"X-CSRF-Token": csrf}).status_code == 403
    consent = client.put(
        f"/api/athletes/{athlete_id}/consent", json={"consent_data": True},
        headers={"X-CSRF-Token": csrf},
    )
    assert consent.status_code == 200
    forbidden_alert_consent = client.put(
        f"/api/athletes/{athlete_id}/consent", json={"consent_alerts": True},
        headers={"X-CSRF-Token": csrf},
    )
    assert forbidden_alert_consent.status_code == 403
    seeded = client.post(
        "/api/demo/seed", json={"athlete_id": athlete_id, "scenario": "overload"},
        headers={"X-CSRF-Token": csrf},
    )
    assert seeded.status_code == 200 and len(seeded.json()["series"]) == 28

    first_chat = client.post(
        "/api/chat", json={"athlete_id": athlete_id, "message": "Come mi alleno oggi?"},
        headers={"X-CSRF-Token": csrf},
    )
    assert first_chat.status_code == 200
    limited_chat = client.post(
        "/api/chat", json={"athlete_id": athlete_id, "message": "Spiegami i dati"},
        headers={"X-CSRF-Token": csrf},
    )
    assert limited_chat.status_code == 429

    with TestClient(app) as second_visitor:
        second_started = second_visitor.post("/api/auth/demo")
        assert second_started.status_code == 200
        second_session = second_visitor.get("/api/auth/session").json()
        second_user = second_session["user"]
        second_athlete = second_session["athletes"][0]
        assert second_user["id"] != user_id
        assert second_athlete["id"] != athlete_id
        assert second_visitor.get(f"/api/athletes/{athlete_id}/dashboard").status_code == 404
        _created_user_ids.append(second_user["id"])
        _created_athlete_ids.append(second_athlete["id"])

    with SessionLocal.begin() as db:
        auth_session = db.query(AuthSession).filter_by(user_id=user_id).one()
        auth_session.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    deleted = purge_expired_data()
    assert deleted["demo_guests"] == 1
    with SessionLocal() as db:
        assert db.get(User, user_id) is None
        assert db.get(Athlete, athlete_id) is None


def test_public_demo_access_is_off_by_default(secured_client):
    assert secured_client.post("/api/auth/demo").status_code == 404


def test_athlete_isolation_and_clinician_write_restrictions(secured_client):
    client = secured_client
    assigned_id, other_id = f"assigned-{uuid.uuid4().hex}", f"other-{uuid.uuid4().hex}"
    athlete_email, athlete_password, _ = create_account("athlete", [assigned_id])
    clinician_email, clinician_password, _ = create_account("clinician", [assigned_id])

    login_response = client.post(
        "/api/auth/login", json={"email": athlete_email, "password": athlete_password}
    )
    csrf = login_response.json()["csrf_token"]
    assert client.get(f"/api/athletes/{other_id}/dashboard").status_code == 404
    assert client.delete(
        f"/api/athletes/{other_id}/data?scope=all", headers={"X-CSRF-Token": csrf}
    ).status_code == 404

    login_response = client.post(
        "/api/auth/login", json={"email": clinician_email, "password": clinician_password}
    )
    csrf = login_response.json()["csrf_token"]
    assert client.get(f"/api/athletes/{assigned_id}/dashboard").status_code == 200
    assert client.put(
        f"/api/athletes/{assigned_id}/consent",
        json={"consent_alerts": False},
        headers={"X-CSRF-Token": csrf},
    ).status_code == 403
    assert client.delete(
        f"/api/athletes/{assigned_id}/data?scope=all", headers={"X-CSRF-Token": csrf}
    ).status_code == 403
    assert client.get("/api/hitl/cases").status_code == 200


def test_athlete_can_update_only_own_profile_with_csrf(secured_client):
    client = secured_client
    athlete_id = f"profile-{uuid.uuid4().hex}"
    email, password, _ = create_account("athlete", [athlete_id])

    login_response = client.post("/api/auth/login", json={"email": email, "password": password})
    csrf = login_response.json()["csrf_token"]
    endpoint = f"/api/athletes/{athlete_id}/profile"

    assert client.put(endpoint, json={"name": "Giulia"}).status_code == 403
    assert client.put(endpoint, json={"name": "   "},
                      headers={"X-CSRF-Token": csrf}).status_code == 422
    assert client.put(endpoint, json={}, headers={"X-CSRF-Token": csrf}).status_code == 422
    updated = client.put(
        endpoint,
        json={"name": "  Giulia Ricci  ", "profile": "master"},
        headers={"X-CSRF-Token": csrf},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Giulia Ricci"
    assert updated.json()["profile"] == "master"
    assert client.put(
        f"/api/athletes/not-assigned/profile",
        json={"name": "Altro"},
        headers={"X-CSRF-Token": csrf},
    ).status_code == 404

    clinician_email, clinician_password, _ = create_account("clinician", [athlete_id])
    clinician_login = client.post(
        "/api/auth/login", json={"email": clinician_email, "password": clinician_password}
    )
    assert client.put(
        endpoint,
        json={"name": "Modifica non consentita"},
        headers={"X-CSRF-Token": clinician_login.json()["csrf_token"]},
    ).status_code == 403


def test_retention_purges_expired_records_but_keeps_open_cases(secured_client):
    client = secured_client
    athlete_id = f"retention-{uuid.uuid4().hex}"
    email, password, user_id = create_account("athlete", [athlete_id])
    old = datetime.now(timezone.utc) - timedelta(days=800)
    with SessionLocal.begin() as session:
        session.add(DailyMetric(athlete_id=athlete_id, day=date.today() - timedelta(days=400), load=1))
        session.add(MemoryNote(athlete_id=athlete_id, kind="summary", text="old",
                               created_at=datetime.now(timezone.utc) - timedelta(days=400)))
        session.add(HitlCase(athlete_id=athlete_id, status="approved", trigger="old", level="yellow",
                             report={}, draft_text="old", reviewed_at=old))
        session.add(HitlCase(athlete_id=athlete_id, status="pending", trigger="pending", level="yellow",
                             report={}, draft_text="pending", created_at=old))
        session.add(AlertLog(athlete_id=athlete_id, channel="sms", body="old", created_at=old))
        session.add_all([
            ConsentEvent(athlete_id=athlete_id, actor_user_id=user_id, consent_type="data_processing",
                         version="v0", granted=True, changed_at=old - timedelta(days=1)),
            ConsentEvent(athlete_id=athlete_id, actor_user_id=user_id, consent_type="data_processing",
                         version="v1", granted=True, changed_at=datetime.now(timezone.utc)),
        ])
        session.add(AuthSession(token_hash="a" * 64, csrf_hash="b" * 64, user_id=user_id,
                                expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)))

    client.post("/api/auth/login", json={"email": email, "password": password})
    deleted = purge_expired_data()
    assert deleted["metrics"] == 1
    assert deleted["memory"] == 1
    assert deleted["cases"] == 1
    assert deleted["alerts"] == 1
    assert deleted["consent_history"] == 1
    assert deleted["sessions"] == 1
    with SessionLocal() as session:
        assert session.query(HitlCase).filter_by(athlete_id=athlete_id, status="pending").count() == 1
        assert session.query(ConsentEvent).filter_by(athlete_id=athlete_id).count() == 1
        assert session.query(AuthSession).filter_by(user_id=user_id).count() == 1


def test_athlete_can_erase_all_and_its_account(secured_client):
    client = secured_client
    athlete_id = f"erase-{uuid.uuid4().hex}"
    email, password, _ = create_account("athlete", [athlete_id])
    login_response = client.post("/api/auth/login", json={"email": email, "password": password})
    result = client.delete(
        f"/api/athletes/{athlete_id}/data?scope=all",
        headers={"X-CSRF-Token": login_response.json()["csrf_token"]},
    )
    assert result.status_code == 200
    assert result.json()["athlete_deleted"] == 1
    assert client.get("/api/auth/session").status_code == 401
    with SessionLocal() as session:
        assert session.get(Athlete, athlete_id) is None


def test_login_rate_limit(secured_client):
    from app import auth

    client = secured_client
    with auth._LOGIN_ATTEMPTS_LOCK:
        auth._LOGIN_ATTEMPTS.clear()
    for _ in range(auth._LOGIN_LIMIT):
        response = client.post(
            "/api/auth/login", json={"email": "missing@example.test", "password": "wrong-password"}
        )
        assert response.status_code == 401
    limited = client.post(
        "/api/auth/login", json={"email": "missing@example.test", "password": "wrong-password"}
    )
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == str(auth._LOGIN_WINDOW_S)


def test_synthetic_wearable_sync_is_incremental_and_idempotent(secured_client):
    client = secured_client
    athlete_id = f"wearable-{uuid.uuid4().hex}"
    email, password, _ = create_account("athlete", [athlete_id])
    login_response = client.post("/api/auth/login", json={"email": email, "password": password})
    headers = {"X-CSRF-Token": login_response.json()["csrf_token"]}

    first = client.post(f"/api/athletes/{athlete_id}/wearable/sync", json={}, headers=headers)
    assert first.status_code == 200
    assert first.json()["provider"] == "synthetic_wearable"
    assert first.json()["synthetic"] is True
    assert first.json()["records_received"] == first.json()["records_accepted"] == 42
    assert first.json()["cursor_day"] == date.today().isoformat()

    with SessionLocal() as session:
        assert session.query(DailyMetric).filter_by(athlete_id=athlete_id).count() == 42
        state = session.query(WearableSyncState).filter_by(athlete_id=athlete_id).one()
        assert state.status == "success" and state.last_success_at is not None
        cursor = state.cursor_day

    second = client.post(f"/api/athletes/{athlete_id}/wearable/sync", json={}, headers=headers)
    assert second.status_code == 200
    assert second.json()["records_received"] == 2
    with SessionLocal() as session:
        assert session.query(DailyMetric).filter_by(athlete_id=athlete_id).count() == 42
        state = session.query(WearableSyncState).filter_by(athlete_id=athlete_id).one()
        assert state.cursor_day == cursor


def test_synthetic_wearable_sync_requires_data_consent(secured_client):
    client = secured_client
    athlete_id = f"wearable-no-consent-{uuid.uuid4().hex}"
    email, password, _ = create_account("athlete", [athlete_id])
    with SessionLocal.begin() as session:
        session.get(Athlete, athlete_id).consent_data = False
    login_response = client.post("/api/auth/login", json={"email": email, "password": password})
    response = client.post(
        f"/api/athletes/{athlete_id}/wearable/sync",
        json={},
        headers={"X-CSRF-Token": login_response.json()["csrf_token"]},
    )
    assert response.status_code == 403
    with SessionLocal() as session:
        assert session.query(DailyMetric).filter_by(athlete_id=athlete_id).count() == 0
        assert session.query(WearableSyncState).filter_by(athlete_id=athlete_id).count() == 0


def test_failed_wearable_sync_does_not_advance_cursor_and_can_retry(secured_client, monkeypatch):
    from app import main
    from app.wearable import fetch_synthetic_records

    client = secured_client
    athlete_id = f"wearable-retry-{uuid.uuid4().hex}"
    email, password, _ = create_account("athlete", [athlete_id])
    login_response = client.post("/api/auth/login", json={"email": email, "password": password})
    headers = {"X-CSRF-Token": login_response.json()["csrf_token"]}
    monkeypatch.setattr(main, "fetch_synthetic_records", lambda *args: [{"bad": "payload"}])

    failed = client.post(f"/api/athletes/{athlete_id}/wearable/sync", json={}, headers=headers)
    assert failed.status_code == 502
    with SessionLocal() as session:
        state = session.query(WearableSyncState).filter_by(athlete_id=athlete_id).one()
        assert state.status == "failed" and state.cursor_day is None
        assert state.last_success_at is None
        assert session.query(DailyMetric).filter_by(athlete_id=athlete_id).count() == 0

    monkeypatch.setattr(main, "fetch_synthetic_records", fetch_synthetic_records)
    retried = client.post(f"/api/athletes/{athlete_id}/wearable/sync", json={}, headers=headers)
    assert retried.status_code == 200 and retried.json()["records_accepted"] == 42
