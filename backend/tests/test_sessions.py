"""Tests for revocable sessions (Phase 3).

Covers the SessionService lifecycle and the end-to-end effect: after logout a
replayed cookie is rejected, and a password change revokes all sessions.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from app.config import get_settings
from app.database.base import Base
from app.database.session import get_db
from app.security.auth import (
    create_session_token,
    hash_password,
    new_session_id,
    verify_session_token_full,
)
from app.security.encryption import generate_key
from app.services.session_service import SessionService
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# --- SessionService (unit) ---------------------------------------------------


def test_create_and_active(db_session: Session) -> None:
    svc = SessionService(db_session)
    jti = new_session_id()
    svc.create(session_id=jti, username="owner", ip="1.2.3.4", user_agent="pytest")
    assert svc.is_active(jti) is True


def test_revoke_makes_inactive(db_session: Session) -> None:
    svc = SessionService(db_session)
    jti = new_session_id()
    svc.create(session_id=jti, username="owner")
    svc.revoke(jti)
    assert svc.is_active(jti) is False


def test_unknown_session_is_inactive(db_session: Session) -> None:
    assert SessionService(db_session).is_active("nope") is False


def test_ip_and_ua_stored_hashed_not_clear(db_session: Session) -> None:
    from app.database.models import UserSession

    svc = SessionService(db_session)
    jti = new_session_id()
    svc.create(session_id=jti, username="owner", ip="203.0.113.9", user_agent="secret-agent")
    row = db_session.get(UserSession, jti)
    assert row is not None
    assert row.ip_hash is not None and row.ip_hash != "203.0.113.9"
    assert row.user_agent_hash is not None and row.user_agent_hash != "secret-agent"


def test_revoke_all(db_session: Session) -> None:
    svc = SessionService(db_session)
    a, b = new_session_id(), new_session_id()
    svc.create(session_id=a, username="owner")
    svc.create(session_id=b, username="owner")
    count = svc.revoke_all("owner")
    assert count == 2
    assert svc.is_active(a) is False and svc.is_active(b) is False


# --- token carries a jti -----------------------------------------------------


def test_token_roundtrips_username_and_jti(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    get_settings.cache_clear()
    jti = new_session_id()
    token = create_session_token("owner", session_id=jti)
    parsed = verify_session_token_full(token)
    assert parsed == ("owner", jti)
    get_settings.cache_clear()


# --- end-to-end: logout truly invalidates ------------------------------------


@pytest.fixture
def owner_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    monkeypatch.setenv("ENCRYPTION_KEY", generate_key())
    monkeypatch.setenv("OWNER_USERNAME", "owner")
    monkeypatch.setenv("OWNER_PASSWORD_HASH", hash_password("correct-horse"))
    get_settings.cache_clear()

    engine: Engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db() -> Iterator[Session]:
        s = factory()
        try:
            yield s
        finally:
            s.close()

    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()


def test_logout_invalidates_session(owner_client: TestClient) -> None:
    login = owner_client.post(
        "/api/v1/auth/login", json={"username": "owner", "password": "correct-horse"}
    )
    assert login.status_code == 200
    assert owner_client.get("/api/v1/auth/me").status_code == 200

    owner_client.post("/api/v1/auth/logout")

    assert owner_client.get("/api/v1/auth/me").status_code == 401


def test_change_password_revokes_sessions(owner_client: TestClient) -> None:
    owner_client.post("/api/v1/auth/login", json={"username": "owner", "password": "correct-horse"})
    resp = owner_client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "correct-horse", "new_password": "a-brand-new-pass"},
    )
    assert resp.status_code == 200
    # After a password change, the existing session is revoked.
    assert owner_client.get("/api/v1/auth/me").status_code == 401
