"""Tests for the ReportService (daily/weekly) and report command routing."""

from __future__ import annotations

import pytest
from app.database.models import Classification, Email, EmailAccount, User
from app.services.reports import ReportService
from app.telegram.commands import is_report_command, report_method_for
from sqlalchemy.orm import Session


@pytest.fixture
def account(db_session: Session) -> EmailAccount:
    user = User(external_ref="owner")
    acct = EmailAccount(
        user=user, provider="fake", email_address="me@example.com", status="connected"
    )
    db_session.add(acct)
    db_session.flush()
    return acct


def _email_with_class(
    db_session: Session, account: EmailAccount, mid: str, category: str, priority: str
) -> None:
    email = Email(account_id=account.id, provider_message_id=mid, content_hash=mid * 8)
    db_session.add(email)
    db_session.flush()
    db_session.add(
        Classification(
            email_id=email.id,
            category=category,
            priority=priority,
            risk_level="low",
            requires_action=(priority in {"critical", "high"}),
            confidence=0.7,
            method="rules",
        )
    )
    db_session.flush()


def test_daily_report_empty(db_session: Session) -> None:
    text = ReportService(db_session).daily()
    assert "Sin actividad" in text


def test_daily_report_counts(db_session: Session, account: EmailAccount) -> None:
    _email_with_class(db_session, account, "d1", "finance", "high")
    _email_with_class(db_session, account, "d2", "work", "medium")
    text = ReportService(db_session).daily()
    assert "INFORME DIARIO" in text
    assert "Correos procesados: 2" in text
    assert "Finanzas: 1" in text
    assert "REQUIERE ATENCIÓN" in text  # the high-priority finance item


def test_weekly_includes_recent(db_session: Session, account: EmailAccount) -> None:
    _email_with_class(db_session, account, "w1", "security", "critical")
    text = ReportService(db_session).weekly()
    assert "INFORME SEMANAL" in text
    assert "Críticos: 1" in text


def test_report_command_routing() -> None:
    assert is_report_command("/hoy") is True
    assert is_report_command("/semana@HeliosBot") is True
    assert is_report_command("/resumen") is False
    assert report_method_for("/hoy") == "daily"
    assert report_method_for("/semana") == "weekly"
    assert report_method_for("/nope") is None
