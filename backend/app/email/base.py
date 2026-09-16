"""HELIOS EYE — Email provider contract (provider-agnostic).

This module defines the *stable* boundary between HELIOS and any concrete email
source (Gmail today; Outlook / IMAP / others tomorrow). Nothing downstream — the
normalizer, the classifier, the agents — should ever import a concrete provider.
They depend only on the abstractions declared here.

Design goals
------------
1. **Provider independence**: adding Outlook must not require changes to the
   pipeline. New providers implement :class:`EmailProvider` and register
   themselves (see ``registry.py``).
2. **Read-only by contract**: the interface exposes *reading* operations only.
   There is deliberately no "send", "delete" or "mark as read" method, matching
   the least-privilege posture (email access is READ-ONLY).
3. **Untrusted data**: everything returned by a provider (subject, body,
   sender, attachment names…) is UNTRUSTED. It is carried in plain data objects
   and must never be interpreted as instructions downstream.

The data objects are intentionally minimal and provider-neutral: each provider
maps its native payload into these shapes so the rest of HELIOS sees one common
vocabulary.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


class ProviderMessageRef(BaseModel):
    """A lightweight pointer to a message inside a provider mailbox.

    Listing is separated from fetching so callers can page cheaply over ids and
    then pull full content only for the messages they actually need (cost and
    bandwidth control). ``provider_message_id`` is the provider's own stable id
    for the message and is what we use for idempotency/dedupe.
    """

    provider_message_id: str = Field(..., description="Provider's stable message id.")
    thread_id: str | None = Field(default=None, description="Conversation/thread id, if any.")


class RawAttachment(BaseModel):
    """Metadata for an attachment. Binary content is intentionally NOT included.

    HELIOS stores only what it needs (filename, type, size, hash reference); the
    raw bytes are handled separately and only when a later phase requires it.
    """

    filename: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None


class RawEmail(BaseModel):
    """A provider-neutral representation of a single email message.

    This is the canonical object every provider must produce. It is *raw* in the
    sense that it is pre-normalization and UNTRUSTED: the body may be HTML, may
    be huge, may contain injection attempts. The normalizer (Phase 5) turns this
    into the stored/analyzable form; nothing here is trusted as instructions.
    """

    provider: str = Field(..., description="Provider key, e.g. 'gmail' or 'outlook'.")
    provider_message_id: str = Field(..., description="Provider's stable message id.")
    thread_id: str | None = None
    sender: str | None = Field(default=None, description="From address (untrusted).")
    recipient: str | None = Field(default=None, description="To address (untrusted).")
    subject: str | None = Field(default=None, description="Subject line (untrusted).")
    sent_at: datetime | None = None
    received_at: datetime | None = None
    body_text: str | None = Field(
        default=None, description="Best-effort plain text body (untrusted)."
    )
    body_html: str | None = Field(
        default=None, description="Original HTML body, if provided (untrusted)."
    )
    snippet: str | None = Field(default=None, description="Short preview supplied by the provider.")
    labels: list[str] = Field(default_factory=list, description="Provider labels/folders.")
    attachments: list[RawAttachment] = Field(default_factory=list)


@runtime_checkable
class EmailProvider(Protocol):
    """Interface every concrete email source must implement.

    Implementations are expected to be constructed with whatever credentials
    they need (via their own factory/config) and then used purely for reading.

    Methods are async because real providers perform network I/O; the fake
    provider used in tests simply returns immediately.
    """

    #: Short, stable identifier for the provider (e.g. "gmail"). Used as the key
    #: in the registry and stored in ``email_accounts.provider``.
    name: str

    async def list_messages(self, *, limit: int = 50) -> list[ProviderMessageRef]:
        """Return references to the most recent messages (newest first).

        Only ids/threads are returned to keep listing cheap. ``limit`` caps how
        many refs come back so a huge mailbox cannot overwhelm the caller.
        """
        ...

    async def fetch_message(self, provider_message_id: str) -> RawEmail:
        """Fetch and map a single message into a :class:`RawEmail`.

        Must not mutate mailbox state (no marking as read). Raises
        :class:`EmailProviderError` on transport/parse failure so callers can
        handle it uniformly regardless of the underlying provider.
        """
        ...


class EmailProviderError(RuntimeError):
    """Raised when a provider cannot list or fetch messages.

    Wrapping provider-specific exceptions in one type lets the pipeline treat
    all providers uniformly (retry, dead-letter, log) without knowing details.
    """
