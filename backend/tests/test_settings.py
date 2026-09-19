"""Tests for the SettingsService and the settings/change-password endpoints."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from app.config import get_settings
from app.database.base import Base
from app.database.models import AppSetting
from app.database.session import get_db
from app.security.auth import hash_password
from app.security.encryption import generate_key
from app.services.settings_service import SettingsService
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture(autouse=True)
def _secrets(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("ENCRYPTION_KEY", generate_key())
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    monkeypatch.setenv("OWNER_USERNAME", "owner")
    monkeypatch.setenv("OWNER_PASSWORD_HASH", hash_password("initial-pass"))
    # A .env fallback value for one key, to test precedence.
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "env-bot-token")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# --- SettingsService (unit, SQLite) ------------------------------------------


def test_set_and_get_effective_encrypts(db_session: Session) -> None:
    svc = SettingsService(db_session)
    svc.set_secret("openai_api_key", "sk-secret-123")
    # Stored value in the row is ciphertext, not the plaintext.
    row = db_session.query(AppSetting).filter_by(key="openai_api_key").one()
    assert row.value != "sk-secret-123"
    assert "sk-secret-123" not in row.value
    # But the effective value decrypts back.
    assert svc.get_effective("openai_api_key") == "sk-secret-123"


def test_db_takes_precedence_over_env(db_session: Session) -> None:
    svc = SettingsService(db_session)
    # No DB value yet → falls back to env.
    assert svc.get_effective("telegram_bot_token") == "env-bot-token"
    # After setting in DB, DB wins.
    svc.set_secret("telegram_bot_token", "db-bot-token")
    assert svc.get_effective("telegram_bot_token") == "db-bot-token"


def test_status_never_leaks_secrets(db_session: Session) -> None:
    svc = SettingsService(db_session)
    svc.set_secret("openai_api_key", "sk-topsecret")
    status = svc.status()
    assert status["openai_api_key"]["configured"] is True
    assert status["openai_api_key"]["source"] == "db"
    # The secret value must not appear anywhere in the status.
    assert "sk-topsecret" not in str(status)


def test_non_secret_key_shows_value(db_session: Session) -> None:
    svc = SettingsService(db_session)
    svc.set_secret("telegram_allowed_user_ids", "111,222")
    status = svc.status()
    assert status["telegram_allowed_user_ids"]["value"] == "111,222"


def test_reject_unknown_key(db_session: Session) -> None:
    with pytest.raises(ValueError):
        SettingsService(db_session).set_secret("database_url", "x")


def test_reject_empty_value(db_session: Session) -> None:
    with pytest.raises(ValueError):
        SettingsService(db_session).set_secret("openai_api_key", "")


def test_delete_falls_back_to_env(db_session: Session) -> None:
    svc = SettingsService(db_session)
    svc.set_secret("telegram_bot_token", "db-token")
    assert svc.get_effective("telegram_bot_token") == "db-token"
    svc.delete("telegram_bot_token")
    assert svc.get_effective("telegram_bot_token") == "env-bot-token"


# --- Endpoints (TestClient with SQLite override) -----------------------------


@pytest.fixture
def client(_secrets: None) -> Iterator[TestClient]:
    engine: Engine = create_engine(
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
    with TestClient(app) as c:
        yield c


def _login(client: TestClient, password: str = "initial-pass") -> None:
    r = client.post("/api/v1/auth/login", json={"username": "owner", "password": password})
    assert r.status_code == 200


def test_settings_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/settings").status_code == 401


def test_settings_status_and_set(client: TestClient) -> None:
    _login(client)
    # Set a secret.
    r = client.put("/api/v1/settings", json={"key": "openai_api_key", "value": "sk-abc"})
    assert r.status_code == 200
    # Status reports configured=db and does not leak the value.
    status = client.get("/api/v1/settings").json()
    assert status["openai_api_key"]["configured"] is True
    assert "sk-abc" not in str(status)


def test_settings_rejects_non_settable_key(client: TestClient) -> None:
    _login(client)
    r = client.put("/api/v1/settings", json={"key": "session_secret", "value": "x"})
    assert r.status_code == 400


def test_change_password_flow(client: TestClient) -> None:
    _login(client)
    # Wrong current password is rejected.
    bad = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "nope", "new_password": "brand-new-pass"},
    )
    assert bad.status_code == 401
    # Correct current password changes it.
    ok = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "initial-pass", "new_password": "brand-new-pass"},
    )
    assert ok.status_code == 200
    # Old password no longer works; new one does.
    client.post("/api/v1/auth/logout")
    assert (
        client.post(
            "/api/v1/auth/login", json={"username": "owner", "password": "initial-pass"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/login", json={"username": "owner", "password": "brand-new-pass"}
        ).status_code
        == 200
    )


def test_change_password_too_short(client: TestClient) -> None:
    _login(client)
    r = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "initial-pass", "new_password": "short"},
    )
    assert r.status_code == 400
