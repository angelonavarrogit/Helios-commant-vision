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
from app.security.masking import redact_codes

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

    # Human labels + emoji for each category (falls back gracefully).
    _CATEGORY_LABELS: dict[str, str] = {
        _FINANCE: "🏦 Finanzas",
        _INSURANCE: "🛡️ Seguros",
        _WORK: "💼 Trabajo",
        _SECURITY: "🔐 Seguridad",
        "subscriptions": "🔔 Suscripciones",
        "travel": "✈️ Viajes",
        "other": "📄 Otros",
    }

    @staticmethod
    def _short(text: str | None, *, limit: int = 60) -> str:
        """Trim a subject/summary to a single readable line.

        Subjects are UNTRUSTED content and may embed OTP/verification codes, so
        every displayed string is passed through ``redact_codes`` first — a
        standalone 4-8 digit code must never be surfaced (security §5).
        """
        if not text:
            return "(sin asunto)"
        clean = redact_codes(" ".join(text.split()))
        return clean if len(clean) <= limit else clean[: limit - 1].rstrip() + "…"

    @staticmethod
    def _sender_name(sender: str | None) -> str:
        """Extract a friendly sender name from a raw From header."""
        if not sender:
            return "remitente desconocido"
        raw = sender.split("<", 1)[0].strip().strip('"')
        return raw or sender.strip()

    def summary(self) -> str:
        """/resumen — an executive briefing in prose (what arrived + what matters)."""
        items = self._repo.recent_briefing_items(limit=80)
        if not items:
            return (
                "🧠 HELIOS — Resumen ejecutivo\n\n"
                "Aún no he analizado correos. En cuanto llegue algo, te lo resumo aquí."
            )

        total = len(items)
        attention = [i for i in items if i.requires_action or i.priority in ("critical", "high")]
        by_cat: dict[str, int] = {}
        for i in items:
            by_cat[i.category] = by_cat.get(i.category, 0) + 1

        lines: list[str] = ["🧠 HELIOS — Resumen ejecutivo", ""]

        # 1) One-line headline.
        if attention:
            lines.append(
                f"Analicé {total} correos recientes. {len(attention)} necesitan tu atención."
            )
        else:
            lines.append(f"Analicé {total} correos recientes. Nada urgente por ahora. 👌")
        lines.append("")

        # 2) What needs attention — with real subjects and the agent's take.
        if attention:
            lines.append("⚠️ Requieren tu atención:")
            for i in attention[:5]:
                who = self._sender_name(i.sender)
                what = self._short(i.subject)
                label = self._CATEGORY_LABELS.get(i.category, i.category)
                lines.append(f"• {label} — {what}")
                lines.append(f"   de {who}")
                note = i.recommended_action or i.summary
                if note:
                    lines.append(f"   → {self._short(note, limit=90)}")
            if len(attention) > 5:
                lines.append(f"…y {len(attention) - 5} más.")
            lines.append("")

        # 3) Digest by area (only areas that actually have mail).
        lines.append("📊 Por área:")
        for cat, count in sorted(by_cat.items(), key=lambda kv: kv[1], reverse=True):
            label = self._CATEGORY_LABELS.get(cat, cat)
            lines.append(f"• {label}: {count}")

        # 4) Subscriptions hint (a common "pending" the user asked about).
        subs = [i for i in items if i.category == "subscriptions"]
        if subs:
            lines.append("")
            lines.append("🔔 Suscripciones detectadas:")
            for i in subs[:3]:
                lines.append(f"• {self._short(i.subject)} ({self._sender_name(i.sender)})")

        lines.append("")
        lines.append("Escribe /pendientes, /finanzas o /buscar <palabra> para profundizar.")
        return "\n".join(lines)

    def urgent(self) -> str:
        """/urgentes — critical/high items, with real subjects."""
        items = [
            i
            for i in self._repo.recent_briefing_items(limit=80)
            if i.priority in ("critical", "high")
        ]
        if not items:
            return "🟢 No hay asuntos urgentes ahora mismo."
        lines = ["🔴 Urgentes:"]
        for i in items[:10]:
            lines.append(f"• {self._short(i.subject)} — {self._sender_name(i.sender)}")
            if i.recommended_action or i.summary:
                lines.append(f"   → {self._short(i.recommended_action or i.summary, limit=90)}")
        return "\n".join(lines)

    def by_category(self, category: str, title: str) -> str:
        """Shared helper for /finanzas, /seguros, /trabajo, /seguridad."""
        items = [i for i in self._repo.recent_briefing_items(limit=80) if i.category == category]
        if not items:
            return f"{title}: sin novedades."
        lines = [f"{title}:"]
        for i in items[:10]:
            flag = " ⚠️" if i.requires_action else ""
            lines.append(f"• {self._short(i.subject)} — {self._sender_name(i.sender)}{flag}")
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
        """/pendientes — items that require action, with real subjects."""
        items = [i for i in self._repo.recent_briefing_items(limit=80) if i.requires_action]
        if not items:
            return "✅ No tienes pendientes por ahora."
        lines = ["📌 Pendientes (requieren tu acción):"]
        for i in items[:10]:
            label = self._CATEGORY_LABELS.get(i.category, i.category)
            lines.append(f"• {label} — {self._short(i.subject)}")
            note = i.recommended_action or i.summary
            if note:
                lines.append(f"   → {self._short(note, limit=90)}")
        return "\n".join(lines)
