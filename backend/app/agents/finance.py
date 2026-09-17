"""HELIOS FINANCE — Finance agent (deterministic, rule-based).

Analyzes emails classified as finance and produces structured findings:
transactions, payments, transfers, deposits/withdrawals, statements, cards,
fees, and charges that look unusual.

Deliberate design choices
-------------------------
- **Deterministic first.** Amount extraction and event typing use regex/keywords
  rather than the LLM. This is more reliable, testable and free for the financial
  case. A future enrichment could add an LLM pass; a seam is noted below.
- **Never declares fraud.** Per requirements, when something looks off the agent
  uses calibrated language ("requiere revisión", "posible anomalía", "operación
  no reconocida") and sets ``needs_review=True`` — it never asserts fraud.
- **Masks identifiers.** Any account/card numbers in extracted detail or summary
  are masked (``**** 1234``); the full PAN is never stored or surfaced.
- **Read-only.** Produces findings only; never moves money or takes action.
"""

from __future__ import annotations

import re

from app.agents.base import AgentResult, AnalysisContext, Finding
from app.email.normalizer import NormalizedEmail
from app.security.masking import mask_number, mask_numbers_in_text

# Event type keywords (ES/EN). Order matters: "unusual charge" is checked before
# the generic "charge" so we can flag review.
_EVENT_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("statement", ("statement", "estado de cuenta")),
    ("transfer", ("transfer", "transferencia", "wire")),
    ("deposit", ("deposit", "depósito", "abono")),
    ("withdrawal", ("withdrawal", "retiro", "cash withdrawal")),
    ("payment", ("payment", "pago", "paid", "bill pay")),
    ("card", ("card", "tarjeta", "credit card", "debit card")),
    ("fee", ("fee", "comisión", "interest", "interés", "charge", "cargo")),
    ("transaction", ("transaction", "transacción", "purchase", "compra")),
)

# Phrases that suggest the user did not recognize an operation → needs review.
_REVIEW_KEYWORDS: tuple[str, ...] = (
    "unrecognized",
    "no reconocida",
    "did you make",
    "no reconoce",
    "suspicious",
    "sospechosa",
    "unusual",
    "inusual",
    "verify this",
    "confirmar esta",
)

# Amount like "$1,234.56", "USD 10.00", "10,00 EUR", "€ 9.99".
_AMOUNT_RE = re.compile(
    r"(?P<cur1>[$€£]|USD|EUR|GBP|MXN)?\s?(?P<amt>\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)\s?(?P<cur2>USD|EUR|GBP|MXN)?",
    re.IGNORECASE,
)

_CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP"}


class FinanceAgent:
    """Detects and structures financial events from an email."""

    name = "finance"

    async def analyze(self, email: NormalizedEmail, ctx: AnalysisContext) -> AgentResult:
        """Return finance findings. Never raises; empty result if nothing found."""
        text = f"{email.subject}\n{email.body_text}"
        lowered = text.lower()

        event_type = self._detect_event_type(lowered)
        if event_type is None:
            # Not obviously financial content: return an empty, low-confidence result.
            return AgentResult(agent_name=self.name, confidence=0.0)

        amount, currency = self._extract_amount(text)
        needs_review = self._needs_review(lowered)

        detail: dict[str, object] = {"event_type": event_type}
        if amount is not None:
            detail["amount"] = amount
        if currency is not None:
            detail["currency"] = currency
        # Mask any account/card number appearing in the text for the record.
        masked = self._first_masked_account(text)
        if masked is not None:
            detail["masked_account"] = masked

        summary = self._summary(event_type, amount, currency, needs_review)

        finding = Finding(
            kind=event_type,
            summary=summary,
            detail=detail,
            needs_review=needs_review,
        )
        return AgentResult(
            agent_name=self.name,
            findings=[finding],
            requires_action=needs_review,
            confidence=0.75,
        )

    # -- detection helpers ----------------------------------------------------

    @staticmethod
    def _detect_event_type(lowered: str) -> str | None:
        for event_type, keywords in _EVENT_KEYWORDS:
            if any(k in lowered for k in keywords):
                return event_type
        return None

    @staticmethod
    def _needs_review(lowered: str) -> bool:
        return any(k in lowered for k in _REVIEW_KEYWORDS)

    @classmethod
    def _extract_amount(cls, text: str) -> tuple[float | None, str | None]:
        """Extract the first plausible amount and currency, if any."""
        for match in _AMOUNT_RE.finditer(text):
            raw = match.group("amt")
            if not raw or not any(ch.isdigit() for ch in raw):
                continue
            value = cls._parse_amount(raw)
            if value is None:
                continue
            currency = cls._normalize_currency(match.group("cur1"), match.group("cur2"))
            return value, currency
        return None, None

    @staticmethod
    def _parse_amount(raw: str) -> float | None:
        """Parse a numeric amount that may use ',' or '.' as decimal/thousands."""
        cleaned = raw.strip()
        # If both separators present, assume the last one is the decimal sep.
        if "," in cleaned and "." in cleaned:
            if cleaned.rfind(",") > cleaned.rfind("."):
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
        elif "," in cleaned:
            # Treat a single comma as decimal if it looks like cents.
            if re.search(r",\d{2}$", cleaned):
                cleaned = cleaned.replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
        try:
            return float(cleaned)
        except ValueError:
            return None

    @staticmethod
    def _normalize_currency(cur1: str | None, cur2: str | None) -> str | None:
        token = (cur1 or cur2 or "").strip().upper()
        if not token:
            return None
        return _CURRENCY_SYMBOLS.get(token, token if token.isalpha() else None)

    @staticmethod
    def _first_masked_account(text: str) -> str | None:
        """Return a masked form of the first long number found, if any."""
        match = re.search(r"(?:\d[ -]?){8,}", text)
        if match is None:
            return None
        return mask_number(match.group(0))

    @staticmethod
    def _summary(
        event_type: str, amount: float | None, currency: str | None, needs_review: bool
    ) -> str:
        """Build a calibrated, human-readable summary. Never says 'fraud'."""
        parts = [f"Detected {event_type}"]
        if amount is not None:
            money = f"{amount:.2f}"
            parts.append(f"for {money} {currency}" if currency else f"for {money}")
        base = " ".join(parts)
        if needs_review:
            # Calibrated language, not an accusation.
            base += " — requiere revisión (posible operación no reconocida)."
        else:
            base += "."
        # Defensive: mask any numbers that leaked into the summary text.
        return mask_numbers_in_text(base)
