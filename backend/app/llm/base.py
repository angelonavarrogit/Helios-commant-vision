"""HELIOS BRAIN — LLM provider abstraction (structured, provider-agnostic).

HELIOS must not be coupled to a single LLM vendor (ADR-003). This module defines
the stable contract every provider implements. The default provider is local
Ollama (ADR-016); OpenAI is opt-in.

Two design decisions matter for security and reliability:

1. **Structured output only.** ``complete_json`` asks the model to fill a
   Pydantic schema and validates the response against it. Anything that does not
   match the schema is rejected. This drastically shrinks the "do what the email
   says" attack surface: the model can only return the fields we defined.

2. **Zone separation in the signature.** ``system`` carries HELIOS instructions
   (trusted); ``user`` carries UNTRUSTED data (email content). Providers must
   keep them in separate message roles and must never merge untrusted content
   into the system instructions. This is the core prompt-injection defense
   (steering §1).
"""

from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class LLMError(RuntimeError):
    """Raised when the LLM call fails or returns unusable output.

    Wrapping all provider/transport/validation failures in one type lets callers
    (e.g. the classifier) degrade gracefully — typically by falling back to the
    rule-based result — without knowing provider details.
    """


class LLMProvider(Protocol):
    """Interface every LLM backend implements."""

    #: Short identifier, e.g. "ollama", "openai", "fake".
    name: str

    async def complete_json(self, *, system: str, user: str, schema: type[SchemaT]) -> SchemaT:
        """Return a validated instance of ``schema``.

        Contract:
        - ``system``: trusted HELIOS instructions.
        - ``user``: UNTRUSTED data to analyze (kept in a separate role).
        - The provider requests JSON output, parses it and validates it against
          ``schema``; on any failure it raises :class:`LLMError`.
        """
        ...
