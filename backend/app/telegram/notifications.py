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


class FakeNotifier:
    """In-memory notifier for tests: records messages instead of sending them."""

    def __init__(self, *, succeed: bool = True) -> None:
        self._succeed = succeed
        self.sent: list[tuple[str, str]] = []  # (priority, text)

    async def send(self, *, text: str, priority: str) -> bool:
        self.sent.append((priority, text))
        return self._succeed


class TelegramNotifier:
    """Delivers alerts to the allow-listed user(s) over Telegram.

    Thin transport: builds a bot from config and sends to each allowed chat id.
    The python-telegram-bot dependency is imported lazily so tests and the rest
    of the app never require it. Never include secrets in `text`.
    """

    async def send(self, *, text: str, priority: str) -> bool:
        from app.config import get_settings
        from app.telegram.authorization import get_allowed_user_ids
        from telegram import Bot

        settings = get_settings()
        if not settings.telegram_bot_token:
            return False
        recipients = get_allowed_user_ids()
        if not recipients:
            return False
        bot = Bot(token=settings.telegram_bot_token)
        delivered = False
        for chat_id in recipients:
            await bot.send_message(chat_id=chat_id, text=text)
            delivered = True
        return delivered
