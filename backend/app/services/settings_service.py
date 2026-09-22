"""HELIOS — Secure runtime settings (Phase 5.8).

Lets the owner configure Class-B secrets (Telegram bot token, OpenAI API key,
Google client id/secret) and the owner password from the UI instead of `.env`.
Values are encrypted at rest (Fernet) and this service never returns a secret's
clear value — only presence and a masked hint.

Precedence
----------
For a given key, a value stored here (DB) takes precedence over the `.env`
fallback. This is why ``get_effective`` is what the rest of the app should call
to resolve a Class-B secret. Class-A secrets (ENCRYPTION_KEY, SESSION_SECRET,
DATABASE_URL) are NEVER stored here — they must stay in `.env` (chicken-and-egg:
the key that decrypts this table cannot live inside it).
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.models import AppSetting
from app.observability import get_logger
from app.security.encryption import decrypt, encrypt

logger = get_logger("app.services.settings")

_TEST_TIMEOUT = 15.0


@dataclass(frozen=True)
class TestResult:
    """Outcome of a connection test. ``detail`` is safe to show (no secrets)."""

    ok: bool
    detail: str


# Keys that may be managed from the UI. Each maps to its `.env` fallback getter.
# The owner password hash is handled separately (change-password endpoint).
MANAGED_KEYS: frozenset[str] = frozenset(
    {
        "telegram_bot_token",
        "telegram_allowed_user_ids",
        "openai_api_key",
        "google_client_id",
        "google_client_secret",
        "owner_password_hash",
    }
)

# Keys whose values are non-secret (shown/returned in clear, e.g. allow-list).
_NON_SECRET_KEYS: frozenset[str] = frozenset({"telegram_allowed_user_ids"})


class SettingsService:
    """Encrypted key/value settings with DB-over-env precedence."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # -- write ----------------------------------------------------------------

    def set_secret(self, key: str, value: str) -> None:
        """Store (or update) a value. Secrets are encrypted before saving."""
        if key not in MANAGED_KEYS:
            raise ValueError(f"unknown setting key: {key}")
        if value == "":
            raise ValueError("refusing to store an empty value")

        is_secret = key not in _NON_SECRET_KEYS
        stored_value = encrypt(value) if is_secret else value

        row = self._session.execute(
            select(AppSetting).where(AppSetting.key == key)
        ).scalar_one_or_none()
        if row is None:
            self._session.add(AppSetting(key=key, value=stored_value, is_secret=is_secret))
        else:
            row.value = stored_value
            row.is_secret = is_secret
        self._session.flush()

    def delete(self, key: str) -> None:
        """Remove a stored setting (falls back to `.env` afterwards)."""
        row = self._session.execute(
            select(AppSetting).where(AppSetting.key == key)
        ).scalar_one_or_none()
        if row is not None:
            self._session.delete(row)
            self._session.flush()

    # -- read -----------------------------------------------------------------

    def _get_raw(self, key: str) -> str | None:
        """Return the decrypted DB value for a key, or None if not stored."""
        row = self._session.execute(
            select(AppSetting).where(AppSetting.key == key)
        ).scalar_one_or_none()
        if row is None:
            return None
        return decrypt(row.value) if row.is_secret else row.value

    def get_effective(self, key: str) -> str:
        """Return the effective value: DB if present, else the `.env` fallback."""
        db_value = self._get_raw(key)
        if db_value is not None:
            return db_value
        return self._env_fallback(key)

    @staticmethod
    def _env_fallback(key: str) -> str:
        settings = get_settings()
        return {
            "telegram_bot_token": settings.telegram_bot_token,
            "telegram_allowed_user_ids": settings.telegram_allowed_user_ids,
            "openai_api_key": settings.openai_api_key,
            "google_client_id": settings.google_client_id,
            "google_client_secret": settings.google_client_secret,
            "owner_password_hash": settings.owner_password_hash,
        }.get(key, "")

    # -- status (no secret leakage) -------------------------------------------

    def status(self) -> dict[str, dict[str, object]]:
        """Return, per managed key, whether it is configured and its source.

        Never returns secret values. For non-secret keys the value is included.
        """
        result: dict[str, dict[str, object]] = {}
        for key in sorted(MANAGED_KEYS):
            if key == "owner_password_hash":
                continue  # handled by the change-password flow, not shown here
            db_value = self._get_raw(key)
            env_value = self._env_fallback(key)
            configured = bool(db_value or env_value)
            source = "db" if db_value else ("env" if env_value else "none")
            entry: dict[str, object] = {"configured": configured, "source": source}
            if key in _NON_SECRET_KEYS and configured:
                entry["value"] = db_value or env_value
            result[key] = entry
        return result

    # -- connection tests (verify a saved secret actually works) --------------

    async def test_connection(self, provider: str) -> TestResult:
        """Verify a provider's effective credentials by calling its API.

        Uses the effective value (DB over env). Never includes the secret in the
        returned detail. Any failure is normalized to a safe, friendly message.
        """
        if provider == "telegram":
            return await self._test_telegram()
        if provider == "openai":
            return await self._test_openai()
        if provider == "ollama":
            return await self._test_ollama()
        return TestResult(ok=False, detail="Proveedor de prueba desconocido.")

    async def _test_telegram(self) -> TestResult:
        token = self.get_effective("telegram_bot_token")
        if not token:
            return TestResult(ok=False, detail="No hay token de Telegram configurado.")
        try:
            async with httpx.AsyncClient(timeout=_TEST_TIMEOUT) as client:
                resp = await client.get(f"https://api.telegram.org/bot{token}/getMe")
            data = resp.json()
            if resp.status_code == 200 and data.get("ok"):
                username = data.get("result", {}).get("username", "")
                return TestResult(ok=True, detail=f"Conectado como @{username}.")
            return TestResult(ok=False, detail="Token de Telegram inválido.")
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("telegram_test_failed", extra={"error": type(exc).__name__})
            return TestResult(ok=False, detail="No se pudo contactar con Telegram.")

    async def _test_openai(self) -> TestResult:
        api_key = self.get_effective("openai_api_key")
        if not api_key:
            return TestResult(ok=False, detail="No hay API key de OpenAI configurada.")
        try:
            async with httpx.AsyncClient(timeout=_TEST_TIMEOUT) as client:
                resp = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
            if resp.status_code == 200:
                return TestResult(ok=True, detail="API key de OpenAI válida.")
            if resp.status_code in (401, 403):
                return TestResult(ok=False, detail="API key de OpenAI inválida.")
            return TestResult(ok=False, detail="OpenAI respondió con un error.")
        except httpx.HTTPError as exc:
            logger.warning("openai_test_failed", extra={"error": type(exc).__name__})
            return TestResult(ok=False, detail="No se pudo contactar con OpenAI.")

    async def _test_ollama(self) -> TestResult:
        settings = get_settings()
        url = settings.ollama_url.rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=_TEST_TIMEOUT) as client:
                resp = await client.get(f"{url}/api/tags")
            if resp.status_code == 200:
                models = [m.get("name", "") for m in resp.json().get("models", [])]
                return TestResult(
                    ok=True, detail=f"Ollama activo. Modelos: {', '.join(models) or 'ninguno'}."
                )
            return TestResult(ok=False, detail="Ollama respondió con un error.")
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("ollama_test_failed", extra={"error": type(exc).__name__})
            return TestResult(ok=False, detail="No se pudo contactar con Ollama.")
