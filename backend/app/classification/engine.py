"""HELIOS BRAIN — Classification engine (hybrid orchestration).

Implements the "rules first, LLM only when needed" policy (ADR-004, RNF-06):

    1. Run the cheap rule classifier.
    2. If its confidence is at/above the threshold, use it (no LLM cost).
    3. Otherwise, if an LLM classifier is configured, ask it. If the LLM fails
       for any reason, fall back to the rule result (never crash the pipeline).
    4. Cache results by content_hash so identical content is not re-analyzed
       (cost control, RNF-06).

Keeping this decision in one place makes cost control explicit and testable.
The engine exposes an async ``classify`` because the LLM path is async; callers
already ``await`` it (the pipeline is async).
"""

from __future__ import annotations

from app.classification.base import Classification
from app.classification.llm_classifier import LLMClassifier
from app.classification.rules import RuleClassifier
from app.email.normalizer import NormalizedEmail
from app.llm.base import LLMError
from app.observability import get_logger

logger = get_logger("app.classification.engine")

# Below this rule confidence, consult the LLM (if configured).
DEFAULT_CONFIDENCE_THRESHOLD = 0.6


class ClassificationEngine:
    """Runs the hybrid classification policy with optional LLM fallback."""

    def __init__(
        self,
        rule_classifier: RuleClassifier | None = None,
        llm_classifier: LLMClassifier | None = None,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    ) -> None:
        self._rules = rule_classifier or RuleClassifier()
        self._llm = llm_classifier
        self._threshold = confidence_threshold
        # Simple in-process cache: content_hash -> Classification.
        self._cache: dict[str, Classification] = {}

    async def classify(self, email: NormalizedEmail) -> Classification:
        """Classify an email using rules first, LLM only when unsure."""
        # Cache hit: identical content was already classified.
        cached = self._cache.get(email.content_hash)
        if cached is not None:
            logger.info("classification_cache_hit", extra={"content_hash": email.content_hash})
            return cached

        result = self._rules.classify(email)

        # LLM fallback only when rules are unsure and an LLM is available.
        if result.confidence < self._threshold and self._llm is not None:
            try:
                result = await self._llm.classify(email)
            except LLMError as exc:
                # Degrade gracefully: keep the rule result, log the reason.
                logger.warning(
                    "llm_classification_failed_fallback_rules",
                    extra={"error": type(exc).__name__},
                )

        self._cache[email.content_hash] = result
        return result
