"""Tests for oauth_state, ConnectionManager and the connection endpoints.

Uses a fake OAuth flow (no network) and an in-memory DB. Covers the security
properties: CSRF state validation, IDOR scoping, and no token leakage.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.config import get_settings
from app.security import decrypt
from app.security.oauth_state import create_state, verify_state
from app.services.connections import (
    ConnectionManager,
    ConnectionStatus,
    TokenResult,
)
from sqlalchemy.orm import Session


@pytest.fixture(autouse=True)
def _secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.security.encryption import generate_key

    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    monkeypatch.setenv("ENCRYPTION_KEY", generate_key())
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class FakeFlow:
    """A fake OAuthFlow that returns a fixed token without any network."""

    def __init__(self, refresh_token: str = "refresh-abc") -> None:
        self._refresh = refresh_token

    def authorization_url(self, *, state: str, redirect_uri: str) -> str:
        return f"https://provider.example/auth?state={state}&redirect_uri={redirect_uri}"

    async def exchange_code(self, *, code: str, redirect_uri: str) -> TokenResult:
        return TokenResult(
            external_account_id="ext-1",
            email_address="user@example.com",
            refresh_token=self._refresh,
            scopes="https://www.googleapis.com/auth/gmail.readonly",
            token_expires_at=datetime.now(UTC),
        )


def _manager(session: Session) -> ConnectionManager:
    return ConnectionManager(session, {"gmail": FakeFlow()})


# --- oauth_state -------------------------------------------------------------


def test_state_roundtrip() -> None:
    state = create_state(user="owner", provider="gmail")
    assert verify_state(state, provider="gmail") == "owner"


def test_state_wrong_provider_rejected() -> None:
    state = create_state(user="owner", provider="gmail")
    assert verify_state(state, provider="outlook") is None


def test_state_tampered_rejected() -> None:
    state = create_state(user="owner", provider="gmail")
    assert verify_state(state[:-3] + "AAA", provider="gmail") is None


# --- ConnectionManager -------------------------------------------------------


async def test_connect_flow_stores_encrypted_token(db_session: Session) -> None:
    mgr = _manager(db_session)
    state = create_state(user="owner", provider="gmail")
    account = await mgr.handle_callback(
        provider="gmail", code="auth-code", state=state, redirect_uri="http://x/cb"
    )
    assert account.status == ConnectionStatus.CONNECTED.value
    assert account.email_address == "user@example.com"
    # Token stored encrypted, recoverable only via decrypt — never in clear.
    assert account.encrypted_refresh_token is not None
    assert account.encrypted_refresh_token != "refresh-abc"
    assert decrypt(account.encrypted_refresh_token) == "refresh-abc"


async def test_callback_bad_state_rejected(db_session: Session) -> None:
    mgr = _manager(db_session)
    from app.services.connections import ConnectionError as ConnError

    with pytest.raises(ConnError):
        await mgr.handle_callback(
            provider="gmail", code="c", state="forged", redirect_uri="http://x/cb"
        )


async def test_idor_scoping(db_session: Session) -> None:
    mgr = _manager(db_session)
    state = create_state(user="owner", provider="gmail")
    account = await mgr.handle_callback(
        provider="gmail", code="c", state=state, redirect_uri="http://x/cb"
    )
    # A different user must not see or disconnect owner's account.
    assert mgr.get_account("intruder", account.id) is None
    assert mgr.disconnect("intruder", account.id) is False
    # The owner can.
    assert mgr.get_account("owner", account.id) is not None
    assert mgr.disconnect("owner", account.id) is True


async def test_disconnect_clears_token(db_session: Session) -> None:
    mgr = _manager(db_session)
    state = create_state(user="owner", provider="gmail")
    account = await mgr.handle_callback(
        provider="gmail", code="c", state=state, redirect_uri="http://x/cb"
    )
    mgr.disconnect("owner", account.id)
    refreshed = mgr.get_account("owner", account.id)
    assert refreshed is not None
    assert refreshed.status == ConnectionStatus.DISCONNECTED.value
    assert refreshed.encrypted_refresh_token is None


# --- Audit log events (Phase 4) ----------------------------------------------


async def test_audit_connection_initiated_written(db_session: Session) -> None:
    """start_oauth must write a CONNECTION_INITIATED audit entry."""
    from app.database.models import AuditLog
    from sqlalchemy import select

    mgr = _manager(db_session)
    mgr.start_oauth(username="owner", provider="gmail", redirect_uri="http://x/cb")
    entries = (
        db_session.execute(select(AuditLog).where(AuditLog.action == "CONNECTION_INITIATED"))
        .scalars()
        .all()
    )
    assert len(entries) == 1
    assert entries[0].actor == "connections:owner"
    assert entries[0].detail_json.get("provider") == "gmail"


async def test_audit_connection_completed_written(db_session: Session) -> None:
    """A successful callback must write a CONNECTION_COMPLETED audit entry."""
    from app.database.models import AuditLog
    from sqlalchemy import select

    mgr = _manager(db_session)
    state = create_state(user="owner", provider="gmail")
    account = await mgr.handle_callback(
        provider="gmail", code="c", state=state, redirect_uri="http://x/cb"
    )
    entries = (
        db_session.execute(select(AuditLog).where(AuditLog.action == "CONNECTION_COMPLETED"))
        .scalars()
        .all()
    )
    assert len(entries) == 1
    assert entries[0].detail_json.get("account_id") == account.id


async def test_audit_connection_failed_bad_state(db_session: Session) -> None:
    """A bad-state callback must write CONNECTION_FAILED (no token exposed)."""
    from app.database.models import AuditLog
    from app.services.connections import ConnectionError as ConnError
    from sqlalchemy import select

    mgr = _manager(db_session)
    with pytest.raises(ConnError):
        await mgr.handle_callback(
            provider="gmail", code="c", state="forged", redirect_uri="http://x/cb"
        )
    entries = (
        db_session.execute(select(AuditLog).where(AuditLog.action == "CONNECTION_FAILED"))
        .scalars()
        .all()
    )
    assert len(entries) == 1
    assert entries[0].detail_json.get("reason") == "bad_state"
    # The audit entry must never contain token material.
    import json

    raw = json.dumps(entries[0].detail_json)
    assert "refresh" not in raw.lower() and "token" not in raw.lower()


async def test_audit_connection_disconnected_written(db_session: Session) -> None:
    """disconnect must write CONNECTION_DISCONNECTED to the audit log."""
    from app.database.models import AuditLog
    from sqlalchemy import select

    mgr = _manager(db_session)
    state = create_state(user="owner", provider="gmail")
    account = await mgr.handle_callback(
        provider="gmail", code="c", state=state, redirect_uri="http://x/cb"
    )
    mgr.disconnect("owner", account.id)
    entries = (
        db_session.execute(select(AuditLog).where(AuditLog.action == "CONNECTION_DISCONNECTED"))
        .scalars()
        .all()
    )
    assert len(entries) == 1
    assert entries[0].detail_json.get("account_id") == account.id
