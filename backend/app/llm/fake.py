"""HELIOS BRAIN — Fake LLM provider (deterministic, for tests).

Returns a pre-programmed response (or raises a pre-programmed error) so the
classifier and engine can be tested without a running model or network. It also
records the last prompt it received, letting tests assert that untrusted content
was passed as data and that the system/user zones were kept separate.
"""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from app.llm.base import LLMError

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class FakeLLMProvider:
    """A deterministic LLM used in tests."""

    name = "fake"

    def __init__(self, response: BaseModel | None = None, error: bool = False) -> None:
        self._response = response
        self._error = error
        # Captured for assertions in tests.
        self.last_system: str | None = None
        self.last_user: str | None = None

    async def complete_json(self, *, system: str, user: str, schema: type[SchemaT]) -> SchemaT:
        self.last_system = system
        self.last_user = user
        if self._error or self._response is None:
            raise LLMError("fake LLM configured to fail")
        # Re-validate through the requested schema to mimic real providers.
        return schema.model_validate(self._response.model_dump())
