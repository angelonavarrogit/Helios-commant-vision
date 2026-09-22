"""Tests for the background email poller service.

Exercise the real cycle logic (list connected accounts -> list messages ->
run the pipeline) with a FakeEmailProvider, and confirm dedup: re-running a
cycle over the same messages must not create duplicates.
"""

from __future__ import annotations

import pytest
from app.database.models import Email, EmailAccount, User
from app.email.base import RawEmail
from app.email.fake import FakeEmailProvider
from app.poller import service as poller_service
from app.poller.service import PollerService
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def _raw(mid: str, **kwargs: object) -> RawEmail:
    base = {"provider": "fake", "provider_message_id": mid}
    base.update(kwargs)
    return RawEmail(**base)  # type: ignore[arg-type]


def _count(session: Session, model: type) -> int:
    return session.execute(select(func.count()).select_from(model)).scalar_one()


@pytest.fixture
def connected_account(db_session: Session) -> EmailAccount:
    user = User(external_ref="owner")
    acct = EmailAccount(
        user=user,
        provider="fake",
        email_address="me@example.com",
        status="connected",
        encrypted_refresh_token="not-a-real-token",  # noqa: S106 - test placeholder
    )
    db_session.add(acct)
    db_session.flush()
    return acct


def _patch(monkeypatch, db_session: Session, provider: FakeEmailProvider) -> None:  # type: ignore[no-untyped-def]
    # The poller opens its own session and builds a provider per account; in
    # tests we redirect both to the in-memory test session and fake provider.
    monkeypatch.setattr(poller_service, "get_sessionmaker", lambda: (lambda: db_session))
    monkeypatch.setattr(poller_service, "_build_provider", lambda _account: provider)


async def test_cycle_processes_new_messages(
    monkeypatch, db_session: Session, connected_account: EmailAccount  # type: ignore[no-untyped-def]
) -> None:
    provider = FakeEmailProvider(
        [
            _raw("m1", subject="Your payment receipt", body_text="Total 10"),
            _raw("m2", subject="New sign-in detected", body_text="A new device"),
        ]
    )
    _patch(monkeypatch, db_session, provider)

    totals = await PollerService(max_messages=25).run_cycle()

    assert totals["accounts"] == 1
    assert totals["new"] == 2
    assert totals["skipped"] == 0
    assert _count(db_session, Email) == 2


async def test_cycle_is_idempotent(
    monkeypatch, db_session: Session, connected_account: EmailAccount  # type: ignore[no-untyped-def]
) -> None:
    provider = FakeEmailProvider([_raw("dup", subject="Statement", body_text="x")])
    _patch(monkeypatch, db_session, provider)
    svc = PollerService(max_messages=25)

    first = await svc.run_cycle()
    second = await svc.run_cycle()

    assert first["new"] == 1
    assert second["new"] == 0  # already seen
    assert second["skipped"] == 1
    assert _count(db_session, Email) == 1  # no duplicate row


async def test_cycle_skips_when_no_connected_accounts(
    monkeypatch, db_session: Session  # type: ignore[no-untyped-def]
) -> None:
    provider = FakeEmailProvider([_raw("x")])
    _patch(monkeypatch, db_session, provider)

    totals = await PollerService(max_messages=25).run_cycle()

    assert totals["accounts"] == 0
    assert totals["new"] == 0
    assert _count(db_session, Email) == 0
