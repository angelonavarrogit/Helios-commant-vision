"""HELIOS BOT — long-polling runner (entrypoint for the bot process).

Starts the python-telegram-bot Application built in ``bot.py`` and keeps it
polling for updates. This is the process that makes the bot actually respond to
messages (/start, /resumen, ...). It runs as its own service so a bot failure
never affects the API (PROP-003: separate worker).

Run:
    python -m app.telegram.run
"""

from __future__ import annotations

from app.config import get_settings
from app.observability import configure_logging, get_logger
from app.telegram.bot import build_application

logger = get_logger("app.telegram.run")


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    if not settings.telegram_bot_token:
        logger.error("telegram_bot_token_missing")
        raise SystemExit("TELEGRAM_BOT_TOKEN is not configured")

    application = build_application()
    logger.info("telegram_bot_starting")
    # run_polling blocks, manages its own event loop, and handles shutdown
    # signals. Only the two static + intelligence command handlers are wired.
    application.run_polling()


if __name__ == "__main__":
    main()
