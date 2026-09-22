"""HELIOS — dashboard service (Phase V0.2, Iteration 3).

Computes the numbers shown on HELIOS COMMAND's dashboard. Every figure is a real
read from the database — nothing here is estimated or faked (project directive:
dashboard numbers are ALWAYS real). Read-only: this service never mutates state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from app.database.models import (
    AgentRun,
    Alert,
    AuditLog,
    Classification,
    Email,
    EmailAccount,
)


@dataclass
class DashboardKpis:
    """Real, DB-backed key figures for the dashboard."""

    connections_total: int = 0
    connections_connected: int = 0
    emails_total: int = 0
    emails_last_7d: int = 0
    alerts_total: int = 0
    alerts_sent: int = 0
    action_required: int = 0
    agent_runs_total: int = 0
    agent_runs_completed: int = 0
    category_counts: dict[str, int] = field(default_factory=dict)
    priority_counts: dict[str, int] = field(default_factory=dict)


@dataclass
class ActivityItem:
    """A single audit-log entry, safe for display."""

    id: int
    timestamp: str
    action: str
    actor: str | None
    request_id: str | None
    email_id: int | None


class DashboardService:
    """Builds dashboard KPIs and the recent-activity feed from real data."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def _count(self, model: type, condition: ColumnElement[bool] | None = None) -> int:
        stmt = select(func.count()).select_from(model)
        if condition is not None:
            stmt = stmt.where(condition)
        return int(self._session.execute(stmt).scalar_one())

    def _group_counts(self, column: InstrumentedAttribute[str]) -> dict[str, int]:
        rows = self._session.execute(select(column, func.count()).group_by(column)).all()
        return {str(row[0]): int(row[1]) for row in rows}

    def kpis(self, *, now: datetime | None = None) -> DashboardKpis:
        """Compute all dashboard KPIs from the database."""
        reference = now or datetime.now(UTC)
        week_ago = reference - timedelta(days=7)
        return DashboardKpis(
            connections_total=self._count(EmailAccount),
            connections_connected=self._count(EmailAccount, EmailAccount.status == "connected"),
            emails_total=self._count(Email),
            emails_last_7d=self._count(Email, Email.created_at >= week_ago),
            alerts_total=self._count(Alert),
            alerts_sent=self._count(Alert, Alert.status == "sent"),
            action_required=self._count(Classification, Classification.requires_action.is_(True)),
            agent_runs_total=self._count(AgentRun),
            agent_runs_completed=self._count(AgentRun, AgentRun.status == "completed"),
            category_counts=self._group_counts(Classification.category),
            priority_counts=self._group_counts(Classification.priority),
        )

    def activity(self, *, limit: int = 20) -> list[ActivityItem]:
        """Return the most recent audit-log entries (newest first)."""
        capped = max(1, min(limit, 100))
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(capped)
        rows = list(self._session.execute(stmt).scalars().all())
        return [
            ActivityItem(
                id=row.id,
                timestamp=row.created_at.isoformat(),
                action=row.action,
                actor=row.actor,
                request_id=row.request_id,
                email_id=row.email_id,
            )
            for row in rows
        ]
