"""HELIOS INSURANCE — Insurance agent (deterministic, rule-based).

Analyzes emails classified as insurance and produces structured findings:
policies, renewals, payments, due dates, claims, coverage changes and pending
documents. Follows the same BaseAgent contract as FinanceAgent (Phase 7).

Design choices
--------------
- **Deterministic.** Keyword detection + shared date extraction
  (``agents.dates``). Reliable, testable, free.
- **Due-date aware.** Renewals/payments/expirations often carry a deadline; the
  agent extracts it into ``due_date`` so the supervisor and notifications can act
  on time-sensitive items.
- **Masks policy references.** A policy number is a sensitive identifier; only a
  masked form is surfaced.
- **Read-only.** Findings only; never modifies a policy or takes action.
"""

from __future__ import annotations

import re

from app.agents.base import AgentResult, AnalysisContext, Finding
from app.agents.dates import extract_due_date
from app.email.normalizer import NormalizedEmail
from app.security.masking import mask_number

# Event type keywords (ES/EN). Order: more specific/urgent first.
_EVENT_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("expiration", ("expires", "expira", "vence", "vencimiento", "due date", "fecha límite")),
    ("renewal", ("renewal", "renovación", "renew", "renovar")),
    ("claim", ("claim", "reclamo", "siniestro")),
    ("coverage_change", ("coverage", "cobertura", "coverage change", "cambio de cobertura")),
    ("payment", ("premium", "prima", "payment due", "pago de", "cuota")),
    ("document_pending", ("document", "documento", "upload", "adjuntar", "pending", "pendiente")),
    ("policy", ("policy", "póliza", "poliza", "insurance", "seguro")),
)

# Phrases that suggest the user must act (missing docs, action required).
_REVIEW_KEYWORDS: tuple[str, ...] = (
    "action required",
    "acción requerida",
    "required",
    "requerido",
    "pending",
    "pendiente",
    "overdue",
    "vencido",
)

# A policy reference like "Policy No. ABC-12345" or "póliza 998877".
# Uses [^\S\n]* (spaces/tabs, not newlines) so a bare "Policy" keyword on a
# subject line cannot absorb a word from the next line. The captured token must
# contain at least one digit (checked in code) to be treated as a real reference.
_POLICY_REF_RE = re.compile(
    r"(?:policy|p[oó]liza)[^\S\n]*(?:no\.?|n[uú]mero|#|:)?[^\S\n]*([A-Z0-9-]{5,})",
    re.IGNORECASE,
)


class InsuranceAgent:
    """Detects and structures insurance events from an email."""

    name = "insurance"

    async def analyze(self, email: NormalizedEmail, ctx: AnalysisContext) -> AgentResult:
        """Return insurance findings. Never raises; empty result if none."""
        text = f"{email.subject}\n{email.body_text}"
        lowered = text.lower()

        event_type = self._detect_event_type(lowered)
        if event_type is None:
            return AgentResult(agent_name=self.name, confidence=0.0)

        due_date = extract_due_date(text)
        needs_review = self._needs_review(lowered) or event_type in {
            "expiration",
            "renewal",
            "document_pending",
        }

        detail: dict[str, object] = {"event_type": event_type}
        if due_date is not None:
            detail["due_date"] = due_date.date().isoformat()
        policy_ref = self._masked_policy_ref(text)
        if policy_ref is not None:
            detail["policy_ref_masked"] = policy_ref

        summary = self._summary(event_type, due_date is not None, needs_review)

        finding = Finding(
            kind=event_type, summary=summary, detail=detail, needs_review=needs_review
        )
        return AgentResult(
            agent_name=self.name,
            findings=[finding],
            requires_action=needs_review,
            confidence=0.75,
        )

    # -- helpers --------------------------------------------------------------

    @staticmethod
    def _detect_event_type(lowered: str) -> str | None:
        for event_type, keywords in _EVENT_KEYWORDS:
            if any(k in lowered for k in keywords):
                return event_type
        return None

    @staticmethod
    def _needs_review(lowered: str) -> bool:
        return any(k in lowered for k in _REVIEW_KEYWORDS)

    @staticmethod
    def _masked_policy_ref(text: str) -> str | None:
        """Return a masked policy reference if one is present.

        Keeps only the last 4 characters of the reference to avoid storing a
        full identifier.
        """
        # Find the first match whose captured token actually contains digits;
        # a purely alphabetic capture (e.g. the word after a bare "Policy") is
        # not a real reference and is skipped.
        for match in _POLICY_REF_RE.finditer(text):
            ref = match.group(1)
            digit_count = sum(ch.isdigit() for ch in ref)
            if digit_count == 0:
                continue
            if digit_count >= 4:
                return mask_number(ref)
            # Alphanumeric ref with few digits: keep last 4 chars.
            return f"**** {ref[-4:]}" if len(ref) >= 4 else "****"
        return None

    @staticmethod
    def _summary(event_type: str, has_due_date: bool, needs_review: bool) -> str:
        base = f"Detected insurance {event_type.replace('_', ' ')}"
        if has_due_date:
            base += " with a due date"
        if needs_review:
            base += " — requiere revisión."
        else:
            base += "."
        return base
