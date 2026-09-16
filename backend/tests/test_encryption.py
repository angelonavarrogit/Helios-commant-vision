"""Tests for encryption-at-rest helpers (Fernet)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from app.config import get_settings
from app.security.encryption import EncryptionError, decrypt, encrypt, generate_key


@pytest.fixture(autouse=True)
def _with_key(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Provide a valid ENCRYPTION_KEY for the duration of each test.

    The settings object is cached with lru_cache, so we clear it and monkeypatch
    the env var before each test, and clear again after.
    """
    key = generate_key()
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_roundtrip() -> None:
    secret = "refresh-token-value-123"
    token = encrypt(secret)
    assert token != secret  # actually encrypted
    assert decrypt(token) == secret


def test_ciphertext_is_not_plaintext() -> None:
    token = encrypt("sensitive")
    assert "sensitive" not in token


def test_refuse_empty() -> None:
    with pytest.raises(EncryptionError):
        encrypt("")


def test_tampered_token_rejected() -> None:
    token = encrypt("value")
    tampered = token[:-2] + ("AA" if not token.endswith("AA") else "BB")
    with pytest.raises(EncryptionError):
        decrypt(tampered)


def test_missing_key_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENCRYPTION_KEY", "")
    get_settings.cache_clear()
    with pytest.raises(EncryptionError):
        encrypt("value")


def test_invalid_key_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENCRYPTION_KEY", "not-a-valid-fernet-key")
    get_settings.cache_clear()
    with pytest.raises(EncryptionError):
        encrypt("value")
