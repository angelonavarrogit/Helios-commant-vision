"""HELIOS BOT — Telegram delivery and command handlers.

Access is restricted to an allow-list of user IDs (least privilege). Command
and authorization logic are pure and testable; the transport layer in `bot.py`
is a thin integration over python-telegram-bot.
"""

from app.telegram.authorization import is_authorized, parse_allowed_user_ids
from app.telegram.commands import help_reply, resolve_command, start_reply

__all__ = [
    "help_reply",
    "is_authorized",
    "parse_allowed_user_ids",
    "resolve_command",
    "start_reply",
]
