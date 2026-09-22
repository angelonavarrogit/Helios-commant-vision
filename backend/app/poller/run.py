"""Entrypoint for the HELIOS email poller (run as `python -m app.poller.run`).

Loads settings + JSON logging (mirrors app.telegram.run), then drives the async
polling loop. The loop only runs when POLL_ENABLED is true, so the same image
can be a no-op elsewhere.
"""

from __future__ import annotations

import asyncio

from app.config import get_settings
from app.observability import configure_logging, get_logger
from app.poller.service import PollerService

logger = get_logger("app.poller.run")


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    if not settings.poll_enabled:
        logger.info("poller_disabled")
        raise SystemExit(0)

    service = PollerService(max_messages=settings.poll_max_messages)
    logger.info(
        "poller_boot",
        extra={
            "interval_seconds": settings.poll_interval_seconds,
            "max_messages": settings.poll_max_messages,
        },
    )
    asyncio.run(service.run_forever(interval_seconds=settings.poll_interval_seconds))


if __name__ == "__main__":
    main()
