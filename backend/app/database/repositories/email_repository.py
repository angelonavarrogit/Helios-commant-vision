"""HELIOS MEMORY — Email repository (idempotent persistence).

Encapsulates all database access for emails and their classification. The
pipeline talks to this repository instead of building queries itself, keeping
persistence concerns in one place (ADR-015: ORM, parameterized queries only).

Idempotency
-----------
The same provider message may be delivered to the pipeline more than once (retries,
N8N re-fires, reprocessing). Storing it twice would create duplicate alerts.
This repository guarantees at-most-one row per ``(account_id, provider_message_id)``
by checking before insert, backed by the unique constraint in the schema.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.classification.base import Classification as ClassificationDTO
from app.database.models import Classification, Email
from app.email.normalizer import NormalizedEmail


class EmailRepository:
    """Persistence operations for emails and their classifications."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_provider_id(self, account_id: int, provider_message_id: str) -> Email | None:
        """Return the stored email for this account+message, or None."""
        stmt = select(Email).where(
            Email.account_id == account_id,
            Email.provider_message_id == provider_message_id,
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def exists(self, account_id: int, provider_message_id: str) -> bool:
        """Cheap existence check used by the pipeline for dedupe."""
        return self.get_by_provider_id(account_id, provider_message_id) is not None

    def store_normalized(self, account_id: int, email: NormalizedEmail) -> tuple[Email, bool]:
        """Insert a normalized email if new. Returns (row, created).

        ``created`` is False when the message already existed (idempotent
        no-op), so callers can skip re-notifying.
        """
        existing = self.get_by_provider_id(account_id, email.provider_message_id)
        if existing is not None:
            return existing, False

        row = Email(
            account_id=account_id,
            provider_message_id=email.provider_message_id,
            thread_id=email.thread_id,
            sender=email.sender or None,
            recipient=email.recipient or None,
            subject=email.subject or None,
            body_text=email.body_text or None,
            snippet=email.snippet or None,
            content_hash=email.content_hash,
            is_processed=False,
        )
        self._session.add(row)
        self._session.flush()  # assign PK without committing
        return row, True

    def save_classification(self, email_id: int, result: ClassificationDTO) -> Classification:
        """Persist the classification result for an email.

        Enum values are stored as their string values so the column stays
        portable (MySQL/SQLite) and human-readable.
        """
        row = Classification(
            email_id=email_id,
            category=result.category.value,
            subcategory=result.subcategory,
            priority=result.priority.value,
            risk_level=result.risk_level.value,
            requires_action=result.requires_action,
            deadline=result.deadline,
            confidence=result.confidence,
            method=result.method.value,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def mark_processed(self, email: Email) -> None:
        """Flag an email as fully processed by the pipeline."""
        email.is_processed = True
        self._session.flush()
