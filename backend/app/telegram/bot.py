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
from app.telegram.commands import (
    is_intelligence_command,
    is_report_command,
    is_status_command,
    query_method_for,
    report_method_for,
    resolve_command,
    unauthorized_reply,
)

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

    # Static commands first (/start, /help).
    reply = resolve_command(command)
    if reply is not None:
        return reply.text

    # Data-backed intelligence commands (/resumen, /urgentes, ...).
    if is_intelligence_command(command):
        return _run_intelligence(command)

    # Report commands (/hoy, /semana).
    if is_report_command(command):
        return _run_report(command)

    # System status command (/estado).
    if is_status_command(command):
        return _run_status()

    # Search command (/buscar <term>) — takes an argument.
    normalized = command.strip().split()[0].lower().split("@", 1)[0] if command.strip() else ""
    if normalized == "/buscar":
        term = command.strip()[len(command.strip().split()[0]) :].strip()
        return _run_search(term)

    return "Comando no reconocido. Usa /help."


def _run_intelligence(command: str) -> str:
    """Answer an intelligence command by querying the database.

    Opens a short-lived DB session, delegates to QueryService, and returns the
    text. Errors degrade to a neutral message (never leak internals).
    """
    method_name = query_method_for(command)
    if method_name is None:
        return "Comando no reconocido. Usa /help."
    try:
        from app.database.session import get_sessionmaker
        from app.services.queries import QueryService

        session = get_sessionmaker()()
        try:
            service = QueryService(session)
            return str(getattr(service, method_name)())
        finally:
            session.close()
    except Exception as exc:  # noqa: BLE001 - never leak internals to the user
        logger.warning("intelligence_query_failed", extra={"error": type(exc).__name__})
        return "No pude consultar esa información ahora. Intenta más tarde."


def _run_report(command: str) -> str:
    """Answer a report command (/hoy, /semana) by querying the database."""
    method_name = report_method_for(command)
    if method_name is None:
        return "Comando no reconocido. Usa /help."
    try:
        from app.database.session import get_sessionmaker
        from app.services.reports import ReportService

        session = get_sessionmaker()()
        try:
            service = ReportService(session)
            return str(getattr(service, method_name)())
        finally:
            session.close()
    except Exception as exc:  # noqa: BLE001 - never leak internals to the user
        logger.warning("report_failed", extra={"error": type(exc).__name__})
        return "No pude generar el informe ahora. Intenta más tarde."


def _run_status() -> str:
    """Answer /estado with a real system-health snapshot."""
    try:
        from app.database.session import get_sessionmaker
        from app.services.status_service import StatusService

        session = get_sessionmaker()()
        try:
            return StatusService(session).as_text()
        finally:
            session.close()
    except Exception as exc:  # noqa: BLE001 - never leak internals to the user
        logger.warning("status_failed", extra={"error": type(exc).__name__})
        return "No pude consultar el estado ahora. Intenta más tarde."


def _run_search(term: str) -> str:
    """Answer /buscar <term> by searching the email memory."""
    try:
        from app.database.session import get_sessionmaker
        from app.services.memory import MemoryService

        session = get_sessionmaker()()
        try:
            return MemoryService(session).search(term)
        finally:
            session.close()
    except Exception as exc:  # noqa: BLE001 - never leak internals to the user
        logger.warning("search_failed", extra={"error": type(exc).__name__})
        return "No pude buscar ahora. Intenta más tarde."


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
    # Register the intelligence commands; each dispatches by its own name.
    intel_cmds = (
        "resumen",
        "urgentes",
        "finanzas",
        "seguros",
        "trabajo",
        "seguridad",
        "pendientes",
    )
    for cmd in (*intel_cmds, "hoy", "semana", "buscar", "estado"):
        application.add_handler(CommandHandler(cmd, _handle_intelligence))
    return application


async def _handle_intelligence(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    # The command text (e.g. "/finanzas") is in the message; reuse the dispatcher.
    message_text = update.message.text if update.message and update.message.text else ""
    await _reply_to_update(update, message_text)
