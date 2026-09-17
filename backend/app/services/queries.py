"""HELIOS — Query service for the Telegram intelligence commands.

Turns stored data (classifications, decisions) into short, safe text answers for
commands like /resumen, /urgentes, /finanzas, etc. This is pure read logic: it
takes a DB session, reads through the repository, and formats text.

Safety
------
Summaries are built from already-sanitized/masked stored fields. This service
never emits secrets or full OTP/security codes (those were redacted upstream by
the SecurityAgent and the sanitizer).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.classification.base import Category
from app.database.repositories.email_repository import EmailRepository

# Category keys used by the per-domain commands.
_FINANCE = Category.FINANCE.value
_INSURANCE = Category.INSURANCE.value
_WORK = Category.WORK.value
_SECURITY = Category.SECURITY.value


class QueryService:
    """Builds text answers for the bot from the database."""

    def __init__(self, session: Session) -> None:
        self._repo = EmailRepository(session)

    # -- individual commands --------------------------------------------------

    def summary(self) -> str:
        """/resumen — a compact daily-style overview."""
        total = self._repo.total_emails()
        pri = self._repo.priority_counts()
        cat = self._repo.category_counts()
        lines = [
            "🧠 HELIOS — Resumen",
            f"📧 Correos procesados: {total}",
            "",
            f"🔴 Críticos: {pri.get('critical', 0)}",
            f"🟠 Altos: {pri.get('high', 0)}",
            f"🟡 Medios: {pri.get('medium', 0)}",
            "",
            f"🏦 Finanzas: {cat.get(_FINANCE, 0)}",
            f"🛡️ Seguros: {cat.get(_INSURANCE, 0)}",
            f"💼 Trabajo: {cat.get(_WORK, 0)}",
            f"🔐 Seguridad: {cat.get(_SECURITY, 0)}",
        ]
        return "\n".join(lines)

    def urgent(self) -> str:
        """/urgentes — critical/high items."""
        items = self._repo.urgent_classifications()
        if not items:
            return "No hay asuntos urgentes."
        lines = ["🔴 Urgentes:"]
        lines += [f"• [{c.priority}] {c.category} (email #{c.email_id})" for c in items]
        return "\n".join(lines)

    def by_category(self, category: str, title: str) -> str:
        """Shared helper for /finanzas, /seguros, /trabajo, /seguridad."""
        items = self._repo.recent_by_category(category)
        if not items:
            return f"{title}: sin novedades."
        lines = [f"{title}:"]
        lines += [
            f"• {c.subcategory or c.category} — prioridad {c.priority} (email #{c.email_id})"
            for c in items
        ]
        return "\n".join(lines)

    def finance(self) -> str:
        return self.by_category(_FINANCE, "🏦 Finanzas")

    def insurance(self) -> str:
        return self.by_category(_INSURANCE, "🛡️ Seguros")

    def work(self) -> str:
        return self.by_category(_WORK, "💼 Trabajo")

    def security(self) -> str:
        return self.by_category(_SECURITY, "🔐 Seguridad")

    def pending(self) -> str:
        """/pendientes — items that require action."""
        items = self._repo.action_required()
        if not items:
            return "No tienes pendientes."
        lines = ["📌 Pendientes:"]
        lines += [f"• {c.category} — prioridad {c.priority} (email #{c.email_id})" for c in items]
        return "\n".join(lines)
