"""Generic base repository.

Provides typed CRUD helpers over a SQLAlchemy model. Concrete repositories
subclass this and add domain-specific queries. All access goes through the ORM
with parameterized queries (never string concatenation) — see ADR-015.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Common CRUD operations for a single ORM model."""

    def __init__(self, session: Session, model: type[ModelT]) -> None:
        self._session = session
        self._model = model

    def add(self, instance: ModelT) -> ModelT:
        self._session.add(instance)
        self._session.flush()  # populate PKs without committing
        return instance

    def get(self, entity_id: int) -> ModelT | None:
        return self._session.get(self._model, entity_id)

    def list(self, *, limit: int = 100, offset: int = 0) -> list[ModelT]:
        stmt = select(self._model).limit(limit).offset(offset)
        return list(self._session.execute(stmt).scalars().all())

    def delete(self, instance: ModelT) -> None:
        self._session.delete(instance)
        self._session.flush()
