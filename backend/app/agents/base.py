"""HELIOS agents — common contract (the pattern every agent follows).

Specialized agents (Finance, Insurance, Work, Security, …) all implement the
same small interface so the orchestrator (Phase 11) can run them uniformly and
the supervisor can consolidate their outputs without knowing their internals.

Contract rules (enforced by convention + review):
- An agent receives a :class:`NormalizedEmail` (UNTRUSTED) plus an
  :class:`AnalysisContext` (the classification and any shared metadata).
- It returns a typed :class:`AgentResult`. It does NOT write to the database and
  does NOT send notifications — those are the pipeline's / supervisor's job.
- It must degrade gracefully on empty/odd input (return an empty result, never
  crash).
- It must never treat email content as instructions, and must mask sensitive
  identifiers in its findings (steering §1, §5).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from app.classification.base import Classification
from app.email.normalizer import NormalizedEmail


class AnalysisContext(BaseModel):
    """Shared, trusted context passed to an agent alongside the email.

    Currently carries the classification; more shared signals can be added later
    without changing the agent signature.
    """

    classification: Classification


class Finding(BaseModel):
    """A single structured observation produced by an agent.

    Kept deliberately generic so every domain agent can express its findings in
    one shape. ``kind`` is the agent-specific finding type (e.g.
    "transaction", "statement"); ``detail`` holds domain fields (already masked).
    """

    kind: str = Field(..., description="Agent-specific finding type.")
    summary: str = Field(..., description="Short, human-readable, calibrated summary.")
    detail: dict[str, object] = Field(
        default_factory=dict, description="Structured, masked domain fields."
    )
    needs_review: bool = Field(
        default=False, description="True when a human should review this item."
    )


class AgentResult(BaseModel):
    """The typed output of one agent for one email."""

    agent_name: str
    findings: list[Finding] = Field(default_factory=list)
    requires_action: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @property
    def has_findings(self) -> bool:
        return bool(self.findings)


@runtime_checkable
class BaseAgent(Protocol):
    """Interface every specialized agent implements."""

    #: Short, stable agent identifier (e.g. "finance").
    name: str

    async def analyze(self, email: NormalizedEmail, ctx: AnalysisContext) -> AgentResult:
        """Analyze an email and return typed findings. Never raises on bad input."""
        ...
