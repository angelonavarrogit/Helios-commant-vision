"""HELIOS — Daily / weekly report service (Phase 13).

Builds a consolidated, human-readable report of what HELIOS processed over a
time window, grouped by priority and category, with a short "needs attention"
section. Pure read logic over the repository; text is safe (built from stored,
already-masked classification fields — no secrets, no OTP).

Used by the Telegram ``/hoy`` and ``/semana`` commands and by a report endpoint.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.classification.base import Category, Priority
from app.database.repositories.email_repository import EmailRepository


class ReportService:
    """Produces daily/weekly summaries from stored classifications."""

    def __init__(self, session: Session) -> None:
        self._repo = EmailRepository(session)

    def daily(self, *, now: datetime | None = None) -> str:
        """Report for the last 24 hours."""
        return self._report_since(hours=24, title="INFORME DIARIO", now=now)

    def weekly(self, *, now: datetime | None = None) -> str:
        """Report for the last 7 days."""
        return self._report_since(hours=24 * 7, title="INFORME SEMANAL", now=now)

    def _report_since(self, *, hours: int, title: str, now: datetime | None) -> str:
        reference = now or datetime.now(UTC)
        since = reference - timedelta(hours=hours)
        items = self._repo.classifications_since(since)

        if not items:
            return f"🧠 HELIOS — {title}\nSin actividad en el periodo."

        priorities = Counter(c.priority for c in items)
        categories = Counter(c.category for c in items)
        attention = [c for c in items if c.requires_action]

        lines = [
            f"🧠 HELIOS — {title}",
            f"📧 Correos procesados: {len(items)}",
            "",
            f"🔴 Críticos: {priorities.get(Priority.CRITICAL.value, 0)}",
            f"🟠 Altos: {priorities.get(Priority.HIGH.value, 0)}",
            f"🟡 Medios: {priorities.get(Priority.MEDIUM.value, 0)}",
            "",
            f"🏦 Finanzas: {categories.get(Category.FINANCE.value, 0)}",
            f"🛡️ Seguros: {categories.get(Category.INSURANCE.value, 0)}",
            f"💼 Trabajo: {categories.get(Category.WORK.value, 0)}",
            f"🔐 Seguridad: {categories.get(Category.SECURITY.value, 0)}",
        ]

        if attention:
            lines.append("")
            lines.append("⚠️ REQUIERE ATENCIÓN")
            for i, c in enumerate(attention[:5], start=1):
                lines.append(f"{i}. {c.category} (prioridad {c.priority}, email #{c.email_id})")

        return "\n".join(lines)
