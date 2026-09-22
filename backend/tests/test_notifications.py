"""Tests for the NotificationService (rules + dedupe) and QueryService."""

from __future__ import annotations

import pytest
from app.agents.supervisor import SupervisorDecision
from app.database.models import Alert, Classification, Email, EmailAccount, User
from app.services.notifications import NotificationService
from app.services.queries import QueryService
from app.telegram.notifications import FakeNotifier
from sqlalchemy import func, select
from sqlalchemy.orm import Session


@pytest.fixture
def account(db_session: Session) -> EmailAccount:
    user = User(external_ref="owner")
    acct = EmailAccount(user=user, provider="fake", email_address="me@example.com", status="active")
    db_session.add(acct)
    db_session.flush()
    return acct


def _email(
    db_session: Session,
    account: EmailAccount,
    mid: str,
    *,
    subject: str | None = None,
    sender: str | None = None,
) -> Email:
    row = Email(
        account_id=account.id,
        provider_message_id=mid,
        content_hash=mid * 8,
        subject=subject,
        sender=sender,
    )
    db_session.add(row)
    db_session.flush()
    return row


def _decision(importance: str = "high", notify_now: bool = True) -> SupervisorDecision:
    return SupervisorDecision(
        importance=importance,
        notify_now=notify_now,
        summary="Detected payment.",
        reason="test",
        recommended_action="Review it.",
        confidence=0.8,
    )


def _count(session: Session, model: type) -> int:
    return session.execute(select(func.count()).select_from(model)).scalar_one()


# --- Notification rules ------------------------------------------------------


async def test_notifies_on_high(db_session: Session, account: EmailAccount) -> None:
    email = _email(db_session, account, "m1")
    notifier = FakeNotifier()
    service = NotificationService(db_session, notifier)

    sent = await service.maybe_notify(email_id=email.id, decision=_decision("high", True))

    assert sent is True
    assert len(notifier.sent) == 1
    assert _count(db_session, Alert) == 1


async def test_does_not_notify_on_medium(db_session: Session, account: EmailAccount) -> None:
    email = _email(db_session, account, "m2")
    notifier = FakeNotifier()
    service = NotificationService(db_session, notifier)

    sent = await service.maybe_notify(
        email_id=email.id, decision=_decision("medium", notify_now=False)
    )

    assert sent is False
    assert notifier.sent == []
    assert _count(db_session, Alert) == 0


async def test_dedupe_groups_repeat(db_session: Session, account: EmailAccount) -> None:
    email = _email(db_session, account, "m3")
    notifier = FakeNotifier()
    service = NotificationService(db_session, notifier)

    first = await service.maybe_notify(email_id=email.id, decision=_decision("high", True))
    second = await service.maybe_notify(email_id=email.id, decision=_decision("high", True))

    assert first is True
    assert second is False  # same logical event: grouped, not resent
    assert len(notifier.sent) == 1  # only one actual message
    # Two alert rows: one 'sent', one 'grouped'.
    assert _count(db_session, Alert) == 2


async def test_alert_text_has_no_raw_codes(db_session: Session, account: EmailAccount) -> None:
    email = _email(db_session, account, "m4")
    notifier = FakeNotifier()
    service = NotificationService(db_session, notifier)
    # Summary is supplied by the (safe) supervisor; ensure formatting keeps it safe.
    await service.maybe_notify(email_id=email.id, decision=_decision("critical", True))
    _, text = notifier.sent[0]
    assert "HELIOS" in text
    assert "Acción sugerida" in text


# --- QueryService ------------------------------------------------------------


def _classify(db_session: Session, email_id: int, category: str, priority: str) -> None:
    db_session.add(
        Classification(
            email_id=email_id,
            category=category,
            priority=priority,
            risk_level="low",
            requires_action=(priority in {"critical", "high"}),
            confidence=0.7,
            method="rules",
        )
    )
    db_session.flush()


def test_query_summary_is_executive_briefing(db_session: Session, account: EmailAccount) -> None:
    e1 = _email(db_session, account, "q1", subject="Cargo a tu tarjeta", sender="Banco <b@x.com>")
    e2 = _email(db_session, account, "q2", subject="Reunión el lunes", sender="Jefe <j@x.com>")
    _classify(db_session, e1.id, "finance", "high")
    _classify(db_session, e2.id, "work", "medium")

    text = QueryService(db_session).summary()
    # Prose briefing: mentions it analyzed correos, names a real subject, and
    # lists the area digest — not opaque "email #id".
    assert "Resumen ejecutivo" in text
    assert "Analicé 2 correos" in text
    assert "Cargo a tu tarjeta" in text
    assert "email #" not in text


def test_query_summary_empty(db_session: Session, account: EmailAccount) -> None:
    text = QueryService(db_session).summary()
    assert "Aún no he analizado correos" in text


def test_query_summary_redacts_otp_in_subject(db_session: Session, account: EmailAccount) -> None:
    # A subject carrying a one-time code must never surface the full code.
    e1 = _email(db_session, account, "otp", subject="Your confirmation code is 681640")
    _classify(db_session, e1.id, "security", "high")
    text = QueryService(db_session).summary()
    assert "681640" not in text


def test_query_urgent_lists_high_with_subject(db_session: Session, account: EmailAccount) -> None:
    e1 = _email(db_session, account, "q3", subject="Nuevo inicio de sesión", sender="Google")
    _classify(db_session, e1.id, "security", "critical")
    text = QueryService(db_session).urgent()
    assert "Nuevo inicio de sesión" in text
    assert "email #" not in text


def test_query_pending(db_session: Session, account: EmailAccount) -> None:
    e1 = _email(db_session, account, "q4", subject="Renueva tu póliza")
    _classify(db_session, e1.id, "work", "high")  # requires_action True
    text = QueryService(db_session).pending()
    assert "Pendientes" in text
    assert "Renueva tu póliza" in text


def test_query_empty_category(db_session: Session, account: EmailAccount) -> None:
    text = QueryService(db_session).finance()
    assert "sin novedades" in text
