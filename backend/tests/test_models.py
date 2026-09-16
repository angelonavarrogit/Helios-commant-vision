"""Tests for ORM models: relationships, cascade, idempotency and JSON columns."""

from __future__ import annotations

import pytest
from app.database.models import (
    AgentResult,
    AgentRun,
    Email,
    EmailAccount,
    User,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def _make_account(session: Session) -> EmailAccount:
    user = User(external_ref="owner-1")
    account = EmailAccount(
        user=user, provider="gmail", email_address="me@example.com", status="active"
    )
    session.add(account)
    session.flush()
    return account


def test_create_user_account_email(db_session: Session) -> None:
    account = _make_account(db_session)
    email = Email(
        account_id=account.id,
        provider_message_id="msg-1",
        sender="bank@example.com",
        subject="Statement",
        content_hash="a" * 64,
    )
    db_session.add(email)
    db_session.commit()

    stored = db_session.execute(select(Email)).scalar_one()
    assert stored.provider_message_id == "msg-1"
    assert stored.is_processed is False
    assert stored.account.email_address == "me@example.com"


def test_duplicate_message_id_rejected(db_session: Session) -> None:
    account = _make_account(db_session)
    db_session.add(Email(account_id=account.id, provider_message_id="dup", content_hash="b" * 64))
    db_session.commit()

    # Same provider_message_id within the same account must violate the unique
    # constraint (idempotency / dedupe guarantee).
    db_session.add(Email(account_id=account.id, provider_message_id="dup", content_hash="c" * 64))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_cascade_delete_account_removes_emails(db_session: Session) -> None:
    account = _make_account(db_session)
    db_session.add(Email(account_id=account.id, provider_message_id="m1", content_hash="d" * 64))
    db_session.commit()

    db_session.delete(account)
    db_session.commit()

    remaining = db_session.execute(select(Email)).scalars().all()
    assert remaining == []


def test_agent_result_json_column(db_session: Session) -> None:
    account = _make_account(db_session)
    email = Email(account_id=account.id, provider_message_id="m2", content_hash="e" * 64)
    db_session.add(email)
    db_session.flush()

    run = AgentRun(email_id=email.id, request_id="req-1", status="running")
    db_session.add(run)
    db_session.flush()

    payload = {"findings": ["possible anomaly"], "requires_action": True}
    db_session.add(AgentResult(agent_run_id=run.id, agent_name="finance", output_json=payload))
    db_session.commit()

    stored = db_session.execute(select(AgentResult)).scalar_one()
    assert stored.output_json == payload
    assert stored.run.request_id == "req-1"
