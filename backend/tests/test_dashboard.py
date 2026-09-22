"""Tests for the HELIOS COMMAND dashboard: KPIs, activity feed, system status.

Covers the DashboardService (real DB counts) and the auth-protected endpoints.
All figures asserted here come from real rows — consistent with the directive
that dashboard numbers are never faked.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from app.config import get_settings
from app.database.base import Base
from app.database.models import (
    AgentRun,
    Alert,
    AuditLog,
    Classification,
    Email,
    EmailAccount,
    User,
)
from app.database.session import get_db
from app.security.auth import hash_password
from app.security.encryption import generate_key
from app.services.dashboard_service import DashboardService
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# --- DashboardService (unit) -------------------------------------------------


def _seed(db_session: Session) -> None:
    user = User(external_ref="owner")
    connected = EmailAccount(
        user=user, provider="gmail", email_address="me@example.com", status="connected"
    )
    disconnected = EmailAccount(
        user=user, provider="gmail", email_address="old@example.com", status="disconnected"
    )
    db_session.add_all([connected, disconnected])
    db_session.flush()

    now = datetime.now(UTC)
    recent = Email(
        account_id=connected.id,
        provider_message_id="m1",
        subject="Reciente",
        content_hash="a" * 8,
    )
    db_session.add(recent)
    db_session.flush()
    # Force an old ingestion date on a second email (outside the 7-day window).
    old = Email(
        account_id=connected.id,
        provider_message_id="m2",
        subject="Viejo",
        content_hash="b" * 8,
    )
    db_session.add(old)
    db_session.flush()
    old.created_at = now - timedelta(days=30)

    db_session.add(
        Classification(
            email_id=recent.id,
            category="finance",
            priority="high",
            risk_level="low",
            requires_action=True,
            method="rules",
        )
    )
    db_session.add(Alert(email_id=recent.id, priority="high", status="sent"))
    db_session.add(Alert(email_id=recent.id, priority="low", status="pending"))
    db_session.add(AgentRun(email_id=recent.id, request_id="r1", status="completed"))
    db_session.add(AgentRun(email_id=recent.id, request_id="r2", status="running"))
    db_session.add(AuditLog(action="email.processed", actor="system", created_at=now))
    db_session.flush()


def test_kpis_are_real_counts(db_session: Session) -> None:
    _seed(db_session)
    k = DashboardService(db_session).kpis()
    assert k.connections_total == 2
    assert k.connections_connected == 1
    assert k.emails_total == 2
    assert k.emails_last_7d == 1  # the 30-day-old email is excluded
    assert k.alerts_total == 2
    assert k.alerts_sent == 1
    assert k.action_required == 1
    assert k.agent_runs_total == 2
    assert k.agent_runs_completed == 1
    assert k.category_counts == {"finance": 1}
    assert k.priority_counts == {"high": 1}


def test_kpis_empty_db_is_all_zero(db_session: Session) -> None:
    k = DashboardService(db_session).kpis()
    assert k.connections_total == 0
    assert k.emails_total == 0
    assert k.alerts_total == 0
    assert k.category_counts == {}


def test_activity_newest_first_and_capped(db_session: Session) -> None:
    base = datetime.now(UTC)
    for i in range(5):
        db_session.add(AuditLog(action=f"event.{i}", created_at=base + timedelta(seconds=i)))
    db_session.flush()
    items = DashboardService(db_session).activity(limit=3)
    assert len(items) == 3
    assert items[0].action == "event.4"  # newest first
    assert items[-1].action == "event.2"


# --- Endpoints (TestClient with SQLite override) -----------------------------


@pytest.fixture(autouse=True)
def _secrets(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    # Pin local env so the session cookie is not "Secure" over the HTTP
    # TestClient (an ambient APP_ENV=prod would otherwise break login).
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("ENCRYPTION_KEY", generate_key())
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    monkeypatch.setenv("OWNER_USERNAME", "owner")
    monkeypatch.setenv("OWNER_PASSWORD_HASH", hash_password("initial-pass"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


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


def _login(client: TestClient) -> None:
    r = client.post("/api/v1/auth/login", json={"username": "owner", "password": "initial-pass"})
    assert r.status_code == 200


def test_kpis_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/dashboard/kpis").status_code == 401


def test_activity_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/dashboard/activity").status_code == 401


def test_system_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/dashboard/system").status_code == 401


def test_kpis_endpoint_returns_zeros_on_empty(client: TestClient) -> None:
    _login(client)
    r = client.get("/api/v1/dashboard/kpis")
    assert r.status_code == 200
    body = r.json()
    assert body["connections_total"] == 0
    assert body["emails_total"] == 0
    assert body["category_counts"] == {}


def test_activity_endpoint_empty(client: TestClient) -> None:
    _login(client)
    r = client.get("/api/v1/dashboard/activity")
    assert r.status_code == 200
    assert r.json() == []


def test_activity_limit_validation(client: TestClient) -> None:
    _login(client)
    assert client.get("/api/v1/dashboard/activity?limit=0").status_code == 422
    assert client.get("/api/v1/dashboard/activity?limit=1000").status_code == 422


def test_system_endpoint_shape(client: TestClient) -> None:
    _login(client)
    r = client.get("/api/v1/dashboard/system")
    assert r.status_code == 200
    body = r.json()
    assert body["core"] is True
    assert "database" in body
    assert body["connected_accounts"] == 0
    assert body["providers"] == []
