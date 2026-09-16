"""HELIOS BRAIN — Classification engine (hybrid orchestration).

The engine implements the "rules first, LLM only when needed" policy (ADR-004,
RNF-06). In Phase 5 only the rule classifier exists, so the engine simply runs
it. The seam for the LLM fallback is already here: when a real
:class:`LLMClassifier` is wired in Phase 6, the engine will consult it whenever
the rule confidence is below ``confidence_threshold``.

Keeping this decision in one place means cost control is explicit and testable,
not scattered across the pipeline.
"""

from __future__ import annotations

from app.classification.base import Classification
from app.classification.rules import RuleClassifier
from app.email.normalizer import NormalizedEmail

# Below this rule confidence, Phase 6 will ask the LLM for a second opinion.
DEFAULT_CONFIDENCE_THRESHOLD = 0.6


class ClassificationEngine:
    """Runs the hybrid classification policy."""

    def __init__(
        self,
        rule_classifier: RuleClassifier | None = None,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    ) -> None:
        self._rules = rule_classifier or RuleClassifier()
        self._threshold = confidence_threshold

    def classify(self, email: NormalizedEmail) -> Classification:
        """Classify an email.

        Phase 5: return the rule result directly. The threshold is retained so
        the LLM fallback (Phase 6) can plug in here without changing callers.
        """
        result = self._rules.classify(email)
        # Phase 6 hook:
        #   if result.confidence < self._threshold and self._llm is not None:
        #       return self._llm.classify(email)
        return result
