"""Tests for production configuration validation (Phase 2, D2/D3).

validate_for_prod() is a fail-closed guard: it returns the NAMES of misconfigured
settings (never their values) so the app can refuse to boot insecurely in prod.
Local/dev must be unaffected.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from app.config import Settings, get_settings


@pytest.fixture(autouse=True)
def _clear_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _prod_settings(**overrides: str) -> Settings:
    base = {
        "app_env": "prod",
        "session_secret": "s",
        "encryption_key": "k",
        "owner_password_hash": "scrypt$abc",
        "service_api_token": "t",
        "database_url": "mysql+pymysql://app:strongpass@mysql:3306/aipic",
        "public_base_url": "https://api.helios.example.com",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def test_local_is_never_flagged() -> None:
    # In local mode the guard is a no-op even with empty secrets.
    s = Settings(app_env="local")
    assert s.validate_for_prod() == []


def test_healthy_prod_config_passes() -> None:
    assert _prod_settings().validate_for_prod() == []


def test_missing_secret_is_flagged_by_name_only() -> None:
    s = _prod_settings(session_secret="")
    problems = s.validate_for_prod()
    assert any("SESSION_SECRET" in p for p in problems)
    # The check must never leak values — only names/messages.
    assert all("scrypt$abc" not in p for p in problems)


def test_all_missing_secrets_flagged() -> None:
    s = _prod_settings(
        session_secret="",
        encryption_key="",
        owner_password_hash="",
        service_api_token="",
    )
    problems = s.validate_for_prod()
    for name in ("SESSION_SECRET", "ENCRYPTION_KEY", "OWNER_PASSWORD_HASH", "SERVICE_API_TOKEN"):
        assert any(name in p for p in problems)


def test_changeme_database_url_is_flagged() -> None:
    s = _prod_settings(database_url="mysql+pymysql://app:changeme@mysql:3306/aipic")
    assert any("DATABASE_URL" in p for p in s.validate_for_prod())


def test_placeholder_database_url_is_flagged() -> None:
    s = _prod_settings(
        database_url="mysql+pymysql://app:__SET_A_STRONG_PASSWORD__@mysql:3306/aipic"
    )
    assert any("DATABASE_URL" in p for p in s.validate_for_prod())


def test_non_https_public_url_is_flagged_in_prod() -> None:
    s = _prod_settings(public_base_url="http://api.helios.example.com")
    assert any("PUBLIC_BASE_URL" in p for p in s.validate_for_prod())
