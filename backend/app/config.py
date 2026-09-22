"""Application configuration.

All configuration comes from environment variables (12-factor). Secrets are
never hardcoded. See `.env.example` for the full list of settings.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings loaded from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # App
    app_env: Literal["local", "prod"] = "local"
    app_name: str = "helios"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    api_host: str = "0.0.0.0"  # noqa: S104 - binding inside container is intended
    api_port: int = 8000

    # Database
    database_url: str = "mysql+pymysql://app:changeme@mysql:3306/aipic"

    # LLM provider (default: local Ollama — ADR-016)
    llm_provider: Literal["ollama", "openai"] = "ollama"
    ollama_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.1"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    llm_max_calls_per_hour: int = 200

    # Telegram (Phase 3)
    telegram_bot_token: str = ""
    telegram_allowed_user_ids: str = ""

    # Google OAuth (Phase 4)
    google_client_id: str = ""
    google_client_secret: str = ""

    # Security
    encryption_key: str = ""
    service_api_token: str = ""

    # HELIOS COMMAND auth (Phase 5.7). Single owner account for the self-hosted
    # app. Password is stored ONLY as a scrypt hash (never in clear).
    owner_username: str = "owner"
    owner_password_hash: str = ""
    session_secret: str = ""
    session_ttl_seconds: int = 60 * 60 * 8  # 8 hours

    # Base URL used to build the OAuth redirect URI (Phase 5.7).
    public_base_url: str = "http://localhost:8000"

    # Comma-separated list of allowed CORS origins for HELIOS COMMAND (frontend).
    # Kept restrictive: only the configured frontend origin(s) may call the API
    # with credentials (cookies). Empty means "no cross-origin allowed".
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # Processing guardrails
    max_email_body_chars: int = Field(default=50_000, ge=1_000)
    # Rate limit for POST /emails/process (calls per minute).
    process_rate_limit_per_minute: int = Field(default=120, ge=1)

    # Background email poller (auto-process new mail without n8n).
    # Enabled explicitly so the loop only runs where wanted (e.g. the poller
    # container). Interval floored to avoid hammering provider APIs.
    poll_enabled: bool = False
    poll_interval_seconds: int = Field(default=300, ge=30)
    poll_max_messages: int = Field(default=25, ge=1, le=500)

    @property
    def is_prod(self) -> bool:
        return self.app_env == "prod"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
