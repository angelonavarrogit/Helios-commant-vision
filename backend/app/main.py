"""Application entrypoint.

Creates and configures the FastAPI application. Business logic lives in the
respective packages; this module only wires things together.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api import auth, connections, health
from app.config import get_settings
from app.observability import configure_logging, get_logger


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown hooks."""
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = get_logger("app.startup")
    logger.info(
        "application_starting",
        extra={"app": settings.app_name, "env": settings.app_env, "version": __version__},
    )
    yield
    logger.info("application_stopping", extra={"app": settings.app_name})


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()
    app = FastAPI(
        title="HELIOS — Personal Intelligence & Awareness System",
        version=__version__,
        # Hide interactive docs in production (reduce surface area).
        docs_url=None if settings.is_prod else "/docs",
        redoc_url=None if settings.is_prod else "/redoc",
        lifespan=lifespan,
    )
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(connections.router)
    return app


app = create_app()
