"""HELIOS BRAIN — Rule-based classifier (cheap, deterministic first pass).

This is the "rules first" half of the hybrid classifier (ADR-004). It inspects
cheap signals — sender domain and keyword hits in subject/body — and returns a
:class:`Classification` with a confidence score. When confidence is high enough
the engine (Phase 6) can skip the LLM entirely, saving cost and latency.

Phase 5 ships a deliberately small, honest rule set. It is not meant to be
clever; it is meant to be correct, fast and free. The LLM fallback in Phase 6
handles everything the rules are unsure about.

Untrusted input note: keywords are matched against the email's text as *data*.
Matching a phrase never causes any action beyond assigning a category.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.classification.base import (
    Category,
    Classification,
    ClassificationMethod,
    Priority,
    RiskLevel,
)
from app.email.normalizer import NormalizedEmail


@dataclass(frozen=True)
class _Rule:
    """A single keyword rule mapping signals to a category/priority."""

    category: Category
    priority: Priority
    keywords: tuple[str, ...]
    risk_level: RiskLevel = RiskLevel.LOW
    requires_action: bool = False


# Small, explicit rule set. Order matters: the first rule that matches wins,
# so more security-sensitive rules come first.
_RULES: tuple[_Rule, ...] = (
    _Rule(
        category=Category.SECURITY,
        priority=Priority.HIGH,
        keywords=(
            "verification code",
            "código de verificación",
            "new sign-in",
            "inicio de sesión",
            "password",
            "contraseña",
            "2fa",
            "one-time",
        ),
        risk_level=RiskLevel.MEDIUM,
        requires_action=True,
    ),
    _Rule(
        category=Category.FINANCE,
        priority=Priority.MEDIUM,
        keywords=(
            "transaction",
            "transacción",
            "payment",
            "pago",
            "invoice",
            "factura",
            "statement",
            "estado de cuenta",
            "card",
            "tarjeta",
            "transfer",
            "transferencia",
        ),
    ),
    _Rule(
        category=Category.INSURANCE,
        priority=Priority.MEDIUM,
        keywords=(
            "policy",
            "póliza",
            "insurance",
            "seguro",
            "renewal",
            "renovación",
            "coverage",
            "cobertura",
            "claim",
            "reclamo",
        ),
    ),
    _Rule(
        category=Category.WORK,
        priority=Priority.MEDIUM,
        keywords=(
            "meeting",
            "reunión",
            "deadline",
            "task",
            "tarea",
            "please review",
            "action required",
            "follow up",
        ),
        requires_action=True,
    ),
    _Rule(
        category=Category.SHOPPING,
        priority=Priority.LOW,
        keywords=(
            "order",
            "pedido",
            "shipped",
            "envío",
            "delivery",
            "entrega",
            "receipt",
            "recibo",
        ),
    ),
    _Rule(
        category=Category.SUBSCRIPTIONS,
        priority=Priority.LOW,
        keywords=(
            "subscription",
            "suscripción",
            "trial",
            "prueba",
            "auto-renew",
            "renovación automática",
        ),
    ),
    _Rule(
        category=Category.TRAVEL,
        priority=Priority.LOW,
        keywords=(
            "flight",
            "vuelo",
            "booking",
            "reserva",
            "itinerary",
            "itinerario",
            "hotel",
            "check-in",
        ),
    ),
)

# Confidence assigned to a rule hit. Below the engine's threshold this still
# invites an LLM second opinion in Phase 6; a clear keyword match is fairly
# reliable, so we use a moderately high value.
_RULE_HIT_CONFIDENCE = 0.7
# Confidence for the fallback "other" classification (low on purpose so the
# engine will prefer the LLM when available).
_FALLBACK_CONFIDENCE = 0.3


class RuleClassifier:
    """Classifies an email using cheap keyword/domain signals."""

    name = "rules"

    def classify(self, email: NormalizedEmail) -> Classification:
        """Return a rule-based Classification (always returns something)."""
        haystack = f"{email.subject}\n{email.body_text}".lower()

        for rule in _RULES:
            if any(keyword in haystack for keyword in rule.keywords):
                return Classification(
                    category=rule.category,
                    priority=rule.priority,
                    risk_level=rule.risk_level,
                    requires_action=rule.requires_action,
                    confidence=_RULE_HIT_CONFIDENCE,
                    method=ClassificationMethod.RULES,
                )

        # Nothing matched: low-confidence "other" so the LLM (Phase 6) can weigh in.
        return Classification(
            category=Category.OTHER,
            priority=Priority.INFORMATIONAL,
            risk_level=RiskLevel.LOW,
            requires_action=False,
            confidence=_FALLBACK_CONFIDENCE,
            method=ClassificationMethod.RULES,
        )
