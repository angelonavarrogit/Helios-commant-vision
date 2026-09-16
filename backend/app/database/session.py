"""Database engine and session management.

Synchronous SQLAlchemy engine using PyMySQL. A single engine is created per
process; sessions are short-lived and provided via `get_db` (FastAPI dependency).
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Return a lazily-created singleton engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,  # detect stale connections
            future=True,
        )
    return _engine


def get_sessionmaker() -> sessionmaker[Session]:
    """Return a lazily-created singleton sessionmaker."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(), autoflush=False, autocommit=False, expire_on_commit=False
        )
    return _SessionLocal


def get_db() -> Iterator[Session]:
    """FastAPI dependency that yields a session and always closes it."""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()


def check_connection() -> bool:
    """Return True if a trivial query succeeds against the database."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 - readiness check must never raise
        return False
