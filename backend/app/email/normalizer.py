"""HELIOS EYE — Normalization: RawEmail -> NormalizedEmail.

Normalization is the bridge between "what a provider gave us" (RawEmail, raw and
UNTRUSTED) and "what HELIOS stores and analyzes" (NormalizedEmail). It:

1. Derives a single plain-text body (from text or HTML, via the parser).
2. Sanitizes and defensively truncates every free-text field.
3. Computes a stable ``content_hash`` (SHA-256) used for dedupe and caching.
4. Records whether the body was truncated and any detected injection markers,
   so the pipeline can audit them.

Everything here is pure: given a RawEmail it returns a NormalizedEmail with no
side effects, which makes it fully unit-testable.
"""

from __future__ import annotations

import hashlib

from pydantic import BaseModel, Field

from app.config import get_settings
from app.email.base import RawEmail
from app.email.parser import derive_body_text
from app.security.sanitization import detect_injection, sanitize

# Subject lines are bounded separately from bodies; RFC-ish upper bound.
_MAX_SUBJECT_CHARS = 998
_MAX_ADDRESS_CHARS = 320


class NormalizedEmail(BaseModel):
    """Canonical, sanitized representation of an email ready for storage.

    Still UNTRUSTED in meaning (the content came from outside), but now bounded,
    cleaned and hashed. Field values are safe to store and to place — inside the
    clearly delimited data zone — into an LLM prompt later.
    """

    provider: str
    provider_message_id: str
    thread_id: str | None = None
    sender: str = ""
    recipient: str = ""
    subject: str = ""
    body_text: str = ""
    snippet: str = ""
    labels: list[str] = Field(default_factory=list)
    content_hash: str = Field(..., description="SHA-256 of the canonical content.")
    body_truncated: bool = False
    injection_markers: list[str] = Field(
        default_factory=list, description="Injection phrases detected (for audit only)."
    )
    sent_at: str | None = None
    received_at: str | None = None


def _hash_content(*parts: str) -> str:
    """Compute a stable SHA-256 hex digest over the given parts.

    A newline separator avoids accidental collisions between concatenated
    fields (e.g. subject vs body boundaries).
    """
    digest = hashlib.sha256()
    digest.update("\n".join(parts).encode("utf-8"))
    return digest.hexdigest()


def normalize(raw: RawEmail) -> NormalizedEmail:
    """Convert a RawEmail into a sanitized, hashed NormalizedEmail."""
    settings = get_settings()
    max_body = settings.max_email_body_chars

    # Derive one plain-text body (prefers text/plain, else HTML-derived text).
    raw_body = derive_body_text(body_text=raw.body_text, body_html=raw.body_html)

    body, truncated = sanitize(raw_body, max_chars=max_body)
    subject, _ = sanitize(raw.subject, max_chars=_MAX_SUBJECT_CHARS)
    sender, _ = sanitize(raw.sender, max_chars=_MAX_ADDRESS_CHARS)
    recipient, _ = sanitize(raw.recipient, max_chars=_MAX_ADDRESS_CHARS)
    snippet, _ = sanitize(raw.snippet, max_chars=512)

    # Detect injection markers on the derived body + subject for auditing.
    markers = detect_injection(f"{subject}\n{body}")

    # Hash over the canonical, sanitized content (stable across re-fetches of the
    # same message). Used for dedupe/caching.
    content_hash = _hash_content(raw.provider, raw.provider_message_id, subject, body)

    return NormalizedEmail(
        provider=raw.provider,
        provider_message_id=raw.provider_message_id,
        thread_id=raw.thread_id,
        sender=sender,
        recipient=recipient,
        subject=subject,
        body_text=body,
        snippet=snippet,
        labels=list(raw.labels),
        content_hash=content_hash,
        body_truncated=truncated,
        injection_markers=markers,
        sent_at=raw.sent_at.isoformat() if raw.sent_at else None,
        received_at=raw.received_at.isoformat() if raw.received_at else None,
    )
