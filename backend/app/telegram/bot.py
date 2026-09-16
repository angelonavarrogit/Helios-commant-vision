"""Telegram transport layer for the HELIOS bot (thin integration).

This module wires the pure command/authorization logic to python-telegram-bot.
It is intentionally minimal: all decisions live in `authorization` and
`commands`. The heavy library is imported lazily inside `build_application` so
the rest of the package (and its tests) never require it to be installed or a
token to be present.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.config import get_settings
from app.observability import get_logger
from app.telegram.authorization import is_authorized
from app.telegram.commands import resolve_command, unauthorized_reply

if TYPE_CHECKING:  # pragma: no cover - typing only
    from telegram import Update
    from telegram.ext import Application, ContextTypes

logger = get_logger("app.telegram.bot")


async def _dispatch(command: str, user_id: int | None) -> str:
    """Authorize then resolve a command to reply text.

    Pure enough to unit-test: given a command and a user id, returns the text
    HELIOS would send. Unauthorized users get a neutral message and the attempt
    is logged (never leaking why access was denied).
    """
    if not is_authorized(user_id):
        logger.warning("unauthorized_telegram_access", extra={"user_id": user_id})
        return unauthorized_reply().text
    reply = resolve_command(command)
    if reply is None:
        return "Comando no reconocido. Usa /help."
    return reply.text


async def _handle_start(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply_to_update(update, "/start")


async def _handle_help(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply_to_update(update, "/help")


async def _reply_to_update(update: Update, command: str) -> None:
    user_id = update.effective_user.id if update.effective_user else None
    text = await _dispatch(command, user_id)
    if update.message is not None:
        await update.message.reply_text(text)


def build_application() -> Application[Any, Any, Any, Any, Any, Any]:
    """Build the python-telegram-bot Application with handlers registered.

    Raises RuntimeError if no bot token is configured. Imported lazily so the
    dependency is only needed when actually running the bot.
    """
    from telegram.ext import Application, CommandHandler

    token = get_settings().telegram_bot_token
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")

    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", _handle_start))
    application.add_handler(CommandHandler("help", _handle_help))
    return application
