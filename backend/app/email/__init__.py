"""HELIOS EYE — Email ingestion, parsing and normalization.

All email content is treated as UNTRUSTED DATA (see docs/security.md and
.kiro/steering/security.md). Downstream code depends only on the abstractions
in :mod:`app.email.base`; concrete providers (Gmail now, Outlook/others later)
register themselves in :mod:`app.email.registry`.

Guidance for adding a new provider: docs/email-providers.md.
"""

from app.email.base import (
    EmailProvider,
    EmailProviderError,
    ProviderMessageRef,
    RawAttachment,
    RawEmail,
)
from app.email.registry import ProviderRegistry, registry

__all__ = [
    "EmailProvider",
    "EmailProviderError",
    "ProviderMessageRef",
    "ProviderRegistry",
    "RawAttachment",
    "RawEmail",
    "registry",
]
