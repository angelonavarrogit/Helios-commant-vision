"""API-level tests for auth gating on the connections endpoints.

Focus on the security boundary that does not require a database: unauthenticated
requests must be rejected, and login must set a working session cookie. The
connection lifecycle itself is covered in test_connections.py against the DB.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from app.config import get_settings
from app.database.base import Base
from app.database.session import get_db
from app.security.auth import hash_password
from app.security.encryption import generate_key
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def owner_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """A TestClient with a known owner and an in-memory DB.

    Login now resolves the password hash with DB-over-env precedence, so the app
    needs a working DB session even for auth. We override get_db with SQLite.
    """
    # Pin local env so the session cookie is not "Secure" over the HTTP
    # TestClient (an ambient APP_ENV=prod would otherwise break login).
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    monkeypatch.setenv("ENCRYPTION_KEY", generate_key())
    monkeypatch.setenv("OWNER_USERNAME", "owner")
    monkeypatch.setenv("OWNER_PASSWORD_HASH", hash_password("correct-horse"))
    get_settings.cache_clear()

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db() -> Iterator[Session]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    get_settings.cache_clear()


def test_providers_requires_auth(owner_client: TestClient) -> None:
    # No session cookie → 401.
    assert owner_client.get("/api/v1/connections/providers").status_code == 401


def test_login_rejects_bad_password(owner_client: TestClient) -> None:
    resp = owner_client.post("/api/v1/auth/login", json={"username": "owner", "password": "wrong"})
    assert resp.status_code == 401


def test_login_then_access_providers(owner_client: TestClient) -> None:
    login = owner_client.post(
        "/api/v1/auth/login", json={"username": "owner", "password": "correct-horse"}
    )
    assert login.status_code == 200
    # The TestClient keeps the session cookie; providers now returns 200.
    resp = owner_client.get("/api/v1/connections/providers")
    assert resp.status_code == 200
    providers = resp.json()
    assert any(p["provider"] == "gmail" for p in providers)


def test_me_reflects_session(owner_client: TestClient) -> None:
    owner_client.post("/api/v1/auth/login", json={"username": "owner", "password": "correct-horse"})
    resp = owner_client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    assert resp.json()["username"] == "owner"


def test_logout_clears_session(owner_client: TestClient) -> None:
    owner_client.post("/api/v1/auth/login", json={"username": "owner", "password": "correct-horse"})
    owner_client.post("/api/v1/auth/logout")
    assert owner_client.get("/api/v1/auth/me").status_code == 401
