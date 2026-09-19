"""Tests for HELIOS COMMAND authentication (owner login + signed sessions)."""

from __future__ import annotations

import pytest
from app.config import get_settings
from app.security.auth import (
    create_session_token,
    hash_password,
    verify_password,
    verify_session_token,
)


@pytest.fixture(autouse=True)
def _session_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SESSION_SECRET", "test-secret-value")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_password_hash_roundtrip() -> None:
    stored = hash_password("s3cret!")
    assert stored.startswith("scrypt$")
    assert verify_password("s3cret!", stored) is True
    assert verify_password("wrong", stored) is False


def test_password_hash_is_not_plaintext() -> None:
    assert "s3cret!" not in hash_password("s3cret!")


def test_verify_bad_stored_format() -> None:
    assert verify_password("x", "not-a-valid-hash") is False


def test_session_token_roundtrip() -> None:
    token = create_session_token("owner")
    assert verify_session_token(token) == "owner"


def test_tampered_session_rejected() -> None:
    token = create_session_token("owner")
    tampered = token[:-3] + "AAA"
    assert verify_session_token(tampered) is None


def test_expired_session_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SESSION_TTL_SECONDS", "-1")  # already expired
    get_settings.cache_clear()
    token = create_session_token("owner")
    assert verify_session_token(token) is None
