"""HELIOS EYE — Email provider registry (multi-provider support).

Why a registry?
---------------
HELIOS is designed to ingest from *several* mailboxes and *several* provider
types (Gmail now; Outlook, IMAP, others later). The rest of the system must be
able to obtain a provider *by name* without importing concrete classes. This
registry is that indirection point.

Each concrete provider registers a **factory** under its ``name`` (e.g.
"gmail"). A factory is a callable that builds a ready-to-use provider instance
from a credentials mapping. Keeping factories (not instances) in the registry
means credentials are supplied per-account at build time, not baked in globally
— important because different accounts have different tokens.

Adding a new provider (e.g. Outlook) is therefore a two-line change plus the
implementation: write ``OutlookProvider`` and call ``register("outlook", factory)``.
No pipeline code changes. See docs/email-providers.md.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from app.email.base import EmailProvider

# A factory takes an opaque credentials mapping and returns a provider instance.
# We keep the credentials type as a Mapping so each provider defines its own
# required keys without the registry needing to know them.
ProviderFactory = Callable[[Mapping[str, Any]], EmailProvider]


class ProviderRegistry:
    """An in-memory map of provider name -> factory.

    A single shared instance (``registry`` below) is used across the app, but
    the class is instantiable so tests can build isolated registries.
    """

    def __init__(self) -> None:
        self._factories: dict[str, ProviderFactory] = {}

    def register(self, name: str, factory: ProviderFactory) -> None:
        """Register a provider factory under ``name``.

        Registering the same name twice is treated as a programming error
        (duplicate provider key) and raises, to avoid silent shadowing.
        """
        key = name.strip().lower()
        if not key:
            raise ValueError("provider name must be non-empty")
        if key in self._factories:
            raise ValueError(f"provider '{key}' is already registered")
        self._factories[key] = factory

    def create(self, name: str, credentials: Mapping[str, Any]) -> EmailProvider:
        """Build a provider instance by name using the given credentials.

        Raises KeyError with the list of known providers when the name is
        unknown, which makes misconfiguration easy to diagnose.
        """
        key = name.strip().lower()
        try:
            factory = self._factories[key]
        except KeyError as exc:
            known = ", ".join(sorted(self._factories)) or "(none registered)"
            raise KeyError(f"unknown email provider '{key}'. Known: {known}") from exc
        return factory(credentials)

    def available(self) -> list[str]:
        """Return the sorted list of registered provider names."""
        return sorted(self._factories)


# Shared application-wide registry. Concrete providers register themselves on
# import (see gmail.py). Importers use this instance.
registry = ProviderRegistry()
