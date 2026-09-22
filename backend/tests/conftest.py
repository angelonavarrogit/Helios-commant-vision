"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from app.database.base import Base
from app.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def _enable_sqlite_fks(dbapi_connection: object, _connection_record: object) -> None:
    """Enforce foreign keys on SQLite (off by default) so cascades work."""
    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """A TestClient bound to a freshly created app instance.

    Pins APP_ENV=local so the production startup guard (validate_for_prod) is a
    no-op under the TestClient lifespan regardless of the ambient environment.
    """
    monkeypatch.setenv("APP_ENV", "local")
    from app.config import get_settings

    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()


@pytest.fixture
def db_engine() -> Iterator[Engine]:
    """An in-memory SQLite engine with the full schema created.

    Uses StaticPool so the same in-memory database is shared across connections
    within a test. SQLAlchemy translates portable column types (including
    func.now()) to the SQLite dialect, so the same models work here and on MySQL.
    """
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(engine, "connect", _enable_sqlite_fks)
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Iterator[Session]:
    """A transactional session bound to the in-memory engine."""
    factory = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
