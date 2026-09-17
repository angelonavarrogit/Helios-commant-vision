"""HELIOS SUPERVISOR — consolidates agent results into one decision.

The supervisor is the single place that decides whether something is important
enough to notify the user now. It takes the classification plus every
:class:`AgentResult` and produces a :class:`SupervisorDecision`.

Hard rule (ADR-020, steering §4)
--------------------------------
The supervisor **only recommends**. It never moves money, changes credentials,
replies to email, or takes any action on the world. ``recommended_action`` is a
suggestion for the user, nothing else. There is deliberately no execution path
here.

Decision logic (deterministic and explainable)
-----------------------------------------------
- ``importance`` is derived from the classification priority, escalated if any
  agent finding needs review.
- ``notify_now`` is true for critical/high importance (immediate Telegram); lower
  importance is summarized/stored instead (notification rules, docs/agents.md §6).
- ``summary``/``reason`` explain *why*, feeding the audit trail ("why did I get
  this alert?").
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.base import AgentResult
from app.classification.base import Classification, Priority

# Map classification priority -> importance label. Importance is the supervisor's
# own consolidated notion (kept as strings mirroring priorities for clarity).
_PRIORITY_ORDER: dict[Priority, int] = {
    Priority.INFORMATIONAL: 0,
    Priority.LOW: 1,
    Priority.MEDIUM: 2,
    Priority.HIGH: 3,
    Priority.CRITICAL: 4,
}
_ORDER_TO_PRIORITY = {v: k for k, v in _PRIORITY_ORDER.items()}


class SupervisorDecision(BaseModel):
    """The consolidated decision for one email."""

    importance: str
    notify_now: bool
    summary: str
    reason: str
    recommended_action: str
    confidence: float = Field(ge=0.0, le=1.0)


class SupervisorAgent:
    """Consolidates agent results and the classification into a decision."""

    name = "supervisor"

    def decide(
        self, classification: Classification, results: list[AgentResult]
    ) -> SupervisorDecision:
        """Produce a SupervisorDecision. Pure, deterministic, no side effects."""
        needs_review = any(f.needs_review for r in results for f in r.findings)
        requires_action = any(r.requires_action for r in results)

        importance = self._importance(classification.priority, escalate=needs_review)
        notify_now = importance in {Priority.CRITICAL, Priority.HIGH}

        summary = self._summary(classification, results)
        reason = self._reason(classification, needs_review)
        recommended_action = self._recommended_action(requires_action, classification)
        confidence = self._confidence(classification, results)

        return SupervisorDecision(
            importance=importance.value,
            notify_now=notify_now,
            summary=summary,
            reason=reason,
            recommended_action=recommended_action,
            confidence=confidence,
        )

    # -- helpers --------------------------------------------------------------

    @staticmethod
    def _importance(priority: Priority, *, escalate: bool) -> Priority:
        """Return importance, bumped up one level if a finding needs review."""
        level = _PRIORITY_ORDER[priority]
        if escalate:
            level = min(level + 1, _PRIORITY_ORDER[Priority.CRITICAL])
        return _ORDER_TO_PRIORITY[level]

    @staticmethod
    def _summary(classification: Classification, results: list[AgentResult]) -> str:
        """Build a short summary from the agent findings (already safe text)."""
        parts = [f.summary for r in results for f in r.findings]
        if not parts:
            return f"Email classified as {classification.category.value}; no specific findings."
        # Findings summaries are already masked/redacted by their agents.
        return " ".join(parts[:3])

    @staticmethod
    def _reason(classification: Classification, needs_review: bool) -> str:
        base = (
            f"Category={classification.category.value}, "
            f"priority={classification.priority.value}, "
            f"method={classification.method.value}."
        )
        if needs_review:
            base += " An agent flagged this for review."
        return base

    @staticmethod
    def _recommended_action(requires_action: bool, classification: Classification) -> str:
        """Recommend (never execute) an action for the user."""
        if not requires_action:
            return "No action needed. Stored for reference."
        return f"Review the {classification.category.value} email; it may require your attention."

    @staticmethod
    def _confidence(classification: Classification, results: list[AgentResult]) -> float:
        """Blend classification and agent confidence into one score."""
        scores = [classification.confidence] + [r.confidence for r in results if r.has_findings]
        return round(sum(scores) / len(scores), 3) if scores else classification.confidence
