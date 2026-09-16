"""Unit tests for the rule classifier and the classification engine."""

from __future__ import annotations

from app.classification.base import Category, ClassificationMethod, Priority
from app.classification.engine import ClassificationEngine
from app.classification.rules import RuleClassifier
from app.email.base import RawEmail
from app.email.normalizer import normalize


def _norm(subject: str = "", body: str = ""):  # type: ignore[no-untyped-def]
    return normalize(
        RawEmail(provider="fake", provider_message_id="m", subject=subject, body_text=body)
    )


def test_rules_detect_finance() -> None:
    result = RuleClassifier().classify(_norm(subject="Your payment receipt"))
    assert result.category == Category.FINANCE
    assert result.method == ClassificationMethod.RULES


def test_rules_detect_security_first() -> None:
    # A security signal should win even alongside other words.
    result = RuleClassifier().classify(_norm(body="Your verification code is 123"))
    assert result.category == Category.SECURITY
    assert result.priority == Priority.HIGH


def test_rules_fallback_other_low_confidence() -> None:
    result = RuleClassifier().classify(_norm(subject="hello", body="just saying hi"))
    assert result.category == Category.OTHER
    assert result.confidence < 0.6


def test_engine_uses_rules() -> None:
    result = ClassificationEngine().classify(_norm(subject="Insurance policy renewal"))
    assert result.category == Category.INSURANCE
