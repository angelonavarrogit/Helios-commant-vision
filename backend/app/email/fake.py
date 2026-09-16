"""HELIOS EYE — In-memory fake email provider (for tests & local dev).

This provider implements the exact :class:`EmailProvider` contract but keeps a
list of :class:`RawEmail` objects in memory instead of talking to any network.

Why it exists
-------------
- Deterministic tests: the whole pipeline (Phase 5+) can be exercised without
  credentials, network, or Google APIs.
- Adversarial fixtures: it lets us feed empty / HTML / huge / injection emails
  through the real code paths.

It is intentionally trivial and side-effect free, mirroring the read-only
contract (no method mutates the given messages).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.email.base import EmailProvider, EmailProviderError, ProviderMessageRef, RawEmail


class FakeEmailProvider(EmailProvider):
    """A provider backed by an in-memory list of messages."""

    name = "fake"

    def __init__(self, messages: list[RawEmail] | None = None) -> None:
        # Store newest-first to mirror how real providers list recent mail.
        self._messages: list[RawEmail] = list(messages or [])

    async def list_messages(self, *, limit: int = 50) -> list[ProviderMessageRef]:
        """Return up to ``limit`` message references (newest first)."""
        return [
            ProviderMessageRef(provider_message_id=m.provider_message_id, thread_id=m.thread_id)
            for m in self._messages[:limit]
        ]

    async def fetch_message(self, provider_message_id: str) -> RawEmail:
        """Return the stored message with the given id, or raise if missing."""
        for message in self._messages:
            if message.provider_message_id == provider_message_id:
                return message
        raise EmailProviderError(f"message '{provider_message_id}' not found")


def fake_factory(credentials: Mapping[str, Any]) -> EmailProvider:
    """Factory compatible with the registry.

    The fake ignores credentials; it exists purely for tests. It accepts an
    optional pre-seeded ``messages`` list passed through the credentials mapping
    so tests can register it and then create seeded instances.
    """
    messages = credentials.get("messages") if credentials else None
    return FakeEmailProvider(messages=messages)
