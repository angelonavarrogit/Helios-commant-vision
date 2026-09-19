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

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.base import AgentResult as AgentResultDTO
from app.agents.supervisor import SupervisorDecision as SupervisorDecisionDTO
from app.classification.base import Classification as ClassificationDTO
from app.database.models import (
    AgentResult,
    AgentRun,
    Alert,
    Classification,
    Email,
    SupervisorDecision,
)
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

    # -- agent run / results / supervisor decision ----------------------------

    def create_agent_run(self, email_id: int, request_id: str) -> AgentRun:
        """Open an agent run record for this email/request."""
        run = AgentRun(
            email_id=email_id,
            request_id=request_id,
            started_at=datetime.now(UTC),
            status="running",
        )
        self._session.add(run)
        self._session.flush()
        return run

    def save_agent_results(self, run_id: int, results: list[AgentResultDTO]) -> None:
        """Persist each agent's result as JSON under the run."""
        for result in results:
            self._session.add(
                AgentResult(
                    agent_run_id=run_id,
                    agent_name=result.agent_name,
                    output_json=result.model_dump(mode="json"),
                    confidence=result.confidence,
                )
            )
        self._session.flush()

    def save_supervisor_decision(
        self, run_id: int, decision: SupervisorDecisionDTO
    ) -> SupervisorDecision:
        """Persist the supervisor's consolidated decision."""
        row = SupervisorDecision(
            agent_run_id=run_id,
            importance=decision.importance,
            notify_now=decision.notify_now,
            summary=decision.summary,
            reason=decision.reason,
            recommended_action=decision.recommended_action,
            confidence=decision.confidence,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def finish_agent_run(self, run: AgentRun, status: str = "completed") -> None:
        """Close an agent run record."""
        run.finished_at = datetime.now(UTC)
        run.status = status
        self._session.flush()

    # -- read queries (for the Telegram intelligence commands) ----------------

    def recent_by_category(self, category: str, *, limit: int = 20) -> list[Classification]:
        """Return recent classifications for a category (newest first)."""
        stmt = (
            select(Classification)
            .where(Classification.category == category)
            .order_by(Classification.id.desc())
            .limit(limit)
        )
        return list(self._session.execute(stmt).scalars().all())

    def urgent_classifications(self, *, limit: int = 20) -> list[Classification]:
        """Return recent critical/high-priority classifications."""
        stmt = (
            select(Classification)
            .where(Classification.priority.in_(("critical", "high")))
            .order_by(Classification.id.desc())
            .limit(limit)
        )
        return list(self._session.execute(stmt).scalars().all())

    def action_required(self, *, limit: int = 20) -> list[Classification]:
        """Return recent classifications that require action (pending items)."""
        stmt = (
            select(Classification)
            .where(Classification.requires_action.is_(True))
            .order_by(Classification.id.desc())
            .limit(limit)
        )
        return list(self._session.execute(stmt).scalars().all())

    def category_counts(self) -> dict[str, int]:
        """Return a map of category -> count across all classifications."""
        stmt = select(Classification.category, func.count()).group_by(Classification.category)
        return {row[0]: row[1] for row in self._session.execute(stmt).all()}

    def priority_counts(self) -> dict[str, int]:
        """Return a map of priority -> count across all classifications."""
        stmt = select(Classification.priority, func.count()).group_by(Classification.priority)
        return {row[0]: row[1] for row in self._session.execute(stmt).all()}

    def total_emails(self) -> int:
        """Return the total number of stored emails."""
        return self._session.execute(select(func.count()).select_from(Email)).scalar_one()

    def search_emails(self, term: str, *, limit: int = 20) -> list[Email]:
        """Structured keyword search over subject and body (case-insensitive).

        Parameterized LIKE (ADR-015: never string-concatenated SQL). The term is
        matched as a literal substring; wildcard characters are escaped so a
        user cannot craft a pattern that scans the whole table.
        """
        cleaned = term.strip()
        if not cleaned:
            return []
        # Escape LIKE wildcards so % and _ are treated literally.
        escaped = cleaned.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        stmt = (
            select(Email)
            .where(
                (Email.subject.ilike(pattern, escape="\\"))
                | (Email.body_text.ilike(pattern, escape="\\"))
            )
            .order_by(Email.id.desc())
            .limit(limit)
        )
        return list(self._session.execute(stmt).scalars().all())

    def classifications_since(self, since: datetime) -> list[Classification]:
        """Return classifications for emails created on/after ``since``.

        Joins to Email.created_at so date filtering reflects when HELIOS
        ingested the message (stable, unlike the email's own headers).
        """
        stmt = (
            select(Classification)
            .join(Email, Classification.email_id == Email.id)
            .where(Email.created_at >= since)
            .order_by(Classification.id.desc())
        )
        return list(self._session.execute(stmt).scalars().all())

    # -- alerts (dedup + persistence) -----------------------------------------

    def alert_exists(self, dedupe_key: str) -> bool:
        """True if an alert with this dedupe key was already recorded.

        Used to avoid sending duplicate alerts for the same logical event.
        """
        stmt = select(Alert.id).where(Alert.dedupe_key == dedupe_key).limit(1)
        return self._session.execute(stmt).first() is not None

    def create_alert(
        self,
        *,
        email_id: int | None,
        priority: str,
        dedupe_key: str,
        group_id: str | None,
        status: str,
    ) -> Alert:
        """Persist an alert record (sent or grouped/suppressed)."""
        alert = Alert(
            email_id=email_id,
            channel="telegram",
            priority=priority,
            dedupe_key=dedupe_key,
            group_id=group_id,
            sent_at=datetime.now(UTC) if status == "sent" else None,
            status=status,
        )
        self._session.add(alert)
        self._session.flush()
        return alert
