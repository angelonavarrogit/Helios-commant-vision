"""Tests for StatusService (real system-status snapshot)."""

from __future__ import annotations

from app.database.models import EmailAccount, User
from app.services.status_service import StatusService
from sqlalchemy.orm import Session


def _account(db_session: Session, provider: str, email: str, status: str) -> None:
    user = User(external_ref=f"owner-{email}")
    db_session.add(EmailAccount(user=user, provider=provider, email_address=email, status=status))
    db_session.flush()


def test_snapshot_counts_only_connected(db_session: Session) -> None:
    _account(db_session, "gmail", "a@example.com", "connected")
    _account(db_session, "gmail", "b@example.com", "disconnected")
    snap = StatusService(db_session).snapshot()
    assert snap.connected_accounts == 1
    assert len(snap.providers) == 2
    assert snap.core is True


def test_snapshot_empty(db_session: Session) -> None:
    snap = StatusService(db_session).snapshot()
    assert snap.connected_accounts == 0
    assert snap.providers == []


def test_as_text_renders_header_and_accounts(db_session: Session) -> None:
    _account(db_session, "gmail", "me@example.com", "connected")
    text = StatusService(db_session).as_text()
    assert "HELIOS — Estado" in text
    assert "Core" in text
    assert "Base de datos" in text
    assert "Cuentas conectadas: 1" in text
    assert "me@example.com" in text
