"""HELIOS BRAIN — Ollama provider (local LLM, default).

Talks to a local Ollama server over HTTP (``/api/chat``) requesting JSON output.
Being local means email content never leaves the environment (ADR-016, maximum
privacy).

Reliability & security notes:
- ``system`` and ``user`` are sent as distinct chat roles; untrusted content
  never enters the system role.
- ``format="json"`` asks Ollama to emit valid JSON; we still validate it against
  the caller's Pydantic schema and raise :class:`LLMError` on any mismatch.
- Uses httpx (already a dependency) with an explicit timeout so a hung model
  cannot block the pipeline indefinitely.
"""

from __future__ import annotations

import json
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.config import get_settings
from app.llm.base import LLMError
from app.observability import get_logger

logger = get_logger("app.llm.ollama")

SchemaT = TypeVar("SchemaT", bound=BaseModel)

# Generous but bounded: local models can be slow, but we must not hang forever.
_REQUEST_TIMEOUT_SECONDS = 60.0


class OllamaProvider:
    """LLM provider backed by a local Ollama server."""

    name = "ollama"

    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        self._base_url = (base_url or settings.ollama_url).rstrip("/")
        self._model = model or settings.ollama_model

    async def complete_json(self, *, system: str, user: str, schema: type[SchemaT]) -> SchemaT:
        """Send a chat request expecting JSON and validate against ``schema``."""
        payload = {
            "model": self._model,
            "format": "json",  # ask Ollama to return valid JSON
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},  # UNTRUSTED, isolated role
            ],
        }
        try:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.post(f"{self._base_url}/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("ollama_request_failed", extra={"error": type(exc).__name__})
            raise LLMError("Ollama request failed") from exc

        content = data.get("message", {}).get("content", "")
        return _parse_and_validate(content, schema)


def _parse_and_validate(content: str, schema: type[SchemaT]) -> SchemaT:
    """Parse JSON text and validate it against ``schema``.

    Any parse or validation error becomes an LLMError so the caller can fall
    back to rules. This is where "the model returned something weird" is contained.
    """
    try:
        raw = json.loads(content)
    except (json.JSONDecodeError, TypeError) as exc:
        raise LLMError("LLM did not return valid JSON") from exc
    try:
        return schema.model_validate(raw)
    except ValidationError as exc:
        raise LLMError("LLM output did not match the expected schema") from exc
