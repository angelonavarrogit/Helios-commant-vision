"""Notification interface for HELIOS (delivery is wired in later phases).

Defines the contract the supervisor/pipeline will use to send alerts. The
concrete Telegram sender and the priority/dedup rules are implemented in
Phase 11/12; this interface exists now so upstream code can depend on a stable
abstraction.
"""

from __future__ import annotations

from typing import Protocol


class Notifier(Protocol):
    """Sends a notification to the user through some channel."""

    async def send(self, *, text: str, priority: str) -> bool:
        """Deliver a message. Returns True on success.

        Implementations must never include secrets or full OTP/security codes
        in `text` (see security steering §5).
        """
        ...
