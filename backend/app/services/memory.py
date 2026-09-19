"""HELIOS MEMORY — structured search over stored events (Phase 15).

Answers questions like "¿qué pasó con el banco?" by searching stored emails by
keyword and returning short, safe summaries. This is the structured (keyword)
tier of memory; semantic (embedding) search is proposed but not implemented yet
(see ADR-028) to avoid adding a vector store before there is a concrete need.

Safety: results are built from stored fields; the subject/snippet are already
sanitized, and any long numbers are masked before display.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.database.repositories.email_repository import EmailRepository
from app.security.masking import mask_numbers_in_text


class MemoryService:
    """Keyword search over the email memory."""

    def __init__(self, session: Session) -> None:
        self._repo = EmailRepository(session)

    def search(self, term: str, *, limit: int = 10) -> str:
        """Return a short text summary of emails matching ``term``."""
        cleaned = term.strip()
        if not cleaned:
            return "Indica un término para buscar. Ej: /buscar banco"

        results = self._repo.search_emails(cleaned, limit=limit)
        if not results:
            return f"Sin resultados para “{cleaned}”."

        lines = [f"🔎 Resultados para “{cleaned}”:"]
        for email in results:
            # Prefer the subject; fall back to a snippet of the body. Mask numbers.
            label = email.subject or (email.body_text or "")[:60] or "(sin asunto)"
            lines.append(f"• {mask_numbers_in_text(label)} (email #{email.id})")
        return "\n".join(lines)
