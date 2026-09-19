"""Tests for MemoryService (structured keyword search)."""

from __future__ import annotations

import pytest
from app.database.models import Email, EmailAccount, User
from app.services.memory import MemoryService
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


def _email(db_session: Session, account: EmailAccount, mid: str, subject: str, body: str) -> None:
    db_session.add(
        Email(
            account_id=account.id,
            provider_message_id=mid,
            subject=subject,
            body_text=body,
            content_hash=mid * 8,
        )
    )
    db_session.flush()


def test_search_finds_by_subject(db_session: Session, account: EmailAccount) -> None:
    _email(db_session, account, "m1", "Tu banco: estado de cuenta", "saldo actual")
    text = MemoryService(db_session).search("banco")
    assert "Resultados para" in text
    assert "email #" in text


def test_search_finds_by_body(db_session: Session, account: EmailAccount) -> None:
    _email(db_session, account, "m2", "Aviso", "renovación de tu póliza de seguro")
    text = MemoryService(db_session).search("póliza")
    assert "email #" in text


def test_search_no_results(db_session: Session, account: EmailAccount) -> None:
    _email(db_session, account, "m3", "Hola", "nada relevante")
    text = MemoryService(db_session).search("inexistente")
    assert "Sin resultados" in text


def test_search_empty_term(db_session: Session) -> None:
    text = MemoryService(db_session).search("   ")
    assert "Indica un término" in text


def test_search_wildcards_are_escaped(db_session: Session, account: EmailAccount) -> None:
    # A term of only wildcards must not match everything (they are escaped).
    _email(db_session, account, "m4", "Real subject", "body")
    text = MemoryService(db_session).search("%")
    assert "Sin resultados" in text


def test_search_masks_numbers(db_session: Session, account: EmailAccount) -> None:
    _email(db_session, account, "m5", "Cargo a 4111111111111234 detectado", "x")
    text = MemoryService(db_session).search("Cargo")
    assert "4111111111111234" not in text
