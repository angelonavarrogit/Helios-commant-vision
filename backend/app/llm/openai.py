"""HELIOS BRAIN — OpenAI provider (opt-in).

Disabled by default; HELIOS uses local Ollama for privacy (ADR-016). This
provider exists so the abstraction is real and switching is a config change, not
a rewrite. When used, only minimized content is sent (data-governance §5).

The OpenAI SDK is imported lazily so the dependency is optional at runtime.
"""

from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.config import get_settings
from app.llm.base import LLMError

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class OpenAIProvider:
    """LLM provider backed by the OpenAI API (opt-in)."""

    name = "openai"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        self._api_key = api_key or settings.openai_api_key
        self._model = model or settings.openai_model
        if not self._api_key:
            raise LLMError("OPENAI_API_KEY is not configured")

    async def complete_json(self, *, system: str, user: str, schema: type[SchemaT]) -> SchemaT:
        """Call OpenAI in JSON mode and validate against ``schema``."""
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise LLMError("openai package is not installed") from exc

        client = AsyncOpenAI(api_key=self._api_key)
        try:
            completion = await client.chat.completions.create(
                model=self._model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},  # UNTRUSTED, isolated role
                ],
            )
            content = completion.choices[0].message.content or ""
        except Exception as exc:  # noqa: BLE001 - normalize any SDK error
            raise LLMError("OpenAI request failed") from exc

        try:
            raw = json.loads(content)
            return schema.model_validate(raw)
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            raise LLMError("OpenAI output was not valid for the schema") from exc
