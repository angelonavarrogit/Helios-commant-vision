"""API tests for POST /api/v1/emails/process (service-token protected)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from app.config import get_settings
from app.database.base import Base
from app.database.models import EmailAccount, User
from app.database.session import get_db
from app.email.base import RawEmail
from app.email.fake import fake_factory
from app.email.registry import registry
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[TestClient, int]]:
    """A TestClient wired to an in-memory DB with a seeded fake account.

    Also registers a 'fake' provider factory (seeded with one message) and sets
    a known service token.
    """
    # Pin local env so the prod startup guard (validate_for_prod) is a no-op
    # under the TestClient lifespan regardless of ambient APP_ENV.
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("SERVICE_API_TOKEN", "svc-token")
    get_settings.cache_clear()

    engine: Engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(
        engine,
        "connect",
        lambda dbapi_conn, _rec: dbapi_conn.cursor().execute("PRAGMA foreign_keys=ON"),
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    # Seed a user + account.
    seed = factory()
    user = User(external_ref="owner")
    account = EmailAccount(
        user=user, provider="fake", email_address="me@example.com", status="connected"
    )
    seed.add(account)
    seed.commit()
    account_id = account.id
    seed.close()

    # Register a fake provider seeded with one message matching the id we'll send.
    if "fake" not in registry.available():
        registry.register("fake", fake_factory)
    # Monkeypatch the endpoint's provider builder to always return a seeded fake.
    from app.api import emails as emails_module

    def _fake_provider(_account: EmailAccount):  # type: ignore[no-untyped-def]
        return fake_factory(
            {
                "messages": [
                    RawEmail(
                        provider="fake",
                        provider_message_id="m1",
                        subject="Your payment receipt",
                        body_text="Total $10",
                    )
                ]
            }
        )

    monkeypatch.setattr(emails_module, "_build_provider", _fake_provider)

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
        yield client, account_id

    get_settings.cache_clear()


def test_process_requires_token(api: tuple[TestClient, int]) -> None:
    client, account_id = api
    resp = client.post(
        "/api/v1/emails/process",
        json={"account_id": account_id, "provider_message_id": "m1"},
    )
    assert resp.status_code == 401


def test_process_with_token(api: tuple[TestClient, int]) -> None:
    client, account_id = api
    resp = client.post(
        "/api/v1/emails/process",
        headers={"X-Service-Token": "svc-token"},
        json={"account_id": account_id, "provider_message_id": "m1"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["created"] is True
    assert body["category"] == "finance"


def test_process_unknown_account(api: tuple[TestClient, int]) -> None:
    client, _ = api
    resp = client.post(
        "/api/v1/emails/process",
        headers={"X-Service-Token": "svc-token"},
        json={"account_id": 9999, "provider_message_id": "m1"},
    )
    assert resp.status_code == 404
