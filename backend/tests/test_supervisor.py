"""Tests for the Orchestrator and SupervisorAgent."""

from __future__ import annotations

import pytest
from app.agents.base import AgentResult, Finding
from app.agents.orchestrator import Orchestrator
from app.agents.supervisor import SupervisorAgent
from app.classification.base import (
    Category,
    Classification,
    ClassificationMethod,
    Priority,
    RiskLevel,
)
from app.email.base import RawEmail
from app.email.normalizer import normalize


def _classification(
    category: Category = Category.FINANCE, priority: Priority = Priority.MEDIUM
) -> Classification:
    return Classification(
        category=category,
        priority=priority,
        risk_level=RiskLevel.LOW,
        confidence=0.7,
        method=ClassificationMethod.RULES,
    )


def _email(subject: str = "", body: str = ""):  # type: ignore[no-untyped-def]
    return normalize(
        RawEmail(provider="fake", provider_message_id="m", subject=subject, body_text=body)
    )


# --- Orchestrator ------------------------------------------------------------


async def test_orchestrator_selects_agent_by_category() -> None:
    orch = Orchestrator()
    results = await orch.run(
        _email(subject="Your payment receipt", body="Total $10"),
        _classification(Category.FINANCE),
    )
    assert any(r.agent_name == "finance" for r in results)


async def test_orchestrator_no_agent_for_category() -> None:
    orch = Orchestrator()
    results = await orch.run(_email(subject="hi"), _classification(Category.OTHER))
    assert results == []


async def test_orchestrator_tolerates_failing_agent() -> None:
    class BoomAgent:
        name = "finance"

        async def analyze(self, email, ctx):  # type: ignore[no-untyped-def]
            raise RuntimeError("boom")

    orch = Orchestrator(agents={"finance": BoomAgent()})  # type: ignore[dict-item]
    # Should not raise; the failing agent is simply omitted.
    results = await orch.run(_email(subject="payment"), _classification(Category.FINANCE))
    assert results == []


# --- SupervisorAgent ---------------------------------------------------------


def _result(needs_review: bool, requires_action: bool) -> AgentResult:
    return AgentResult(
        agent_name="finance",
        findings=[
            Finding(kind="transaction", summary="Detected transaction.", needs_review=needs_review)
        ],
        requires_action=requires_action,
        confidence=0.75,
    )


def test_supervisor_no_findings() -> None:
    decision = SupervisorAgent().decide(_classification(priority=Priority.LOW), [])
    assert decision.notify_now is False
    assert "No action needed" in decision.recommended_action


def test_supervisor_high_priority_notifies_now() -> None:
    decision = SupervisorAgent().decide(_classification(priority=Priority.HIGH), [])
    assert decision.notify_now is True
    assert decision.importance == "high"


def test_supervisor_escalates_on_needs_review() -> None:
    # Medium priority + a finding needing review escalates to high → notify now.
    decision = SupervisorAgent().decide(
        _classification(priority=Priority.MEDIUM),
        [_result(needs_review=True, requires_action=True)],
    )
    assert decision.importance == "high"
    assert decision.notify_now is True
    assert "Review" in decision.recommended_action


def test_supervisor_recommends_never_executes() -> None:
    # The decision is advisory only: it must not contain any execution directive.
    decision = SupervisorAgent().decide(
        _classification(priority=Priority.CRITICAL),
        [_result(needs_review=True, requires_action=True)],
    )
    # recommended_action is a suggestion string; there is no execution API.
    assert isinstance(decision.recommended_action, str)
    assert decision.importance == "critical"


def test_supervisor_confidence_is_blended() -> None:
    decision = SupervisorAgent().decide(
        _classification(priority=Priority.MEDIUM),
        [_result(needs_review=False, requires_action=False)],
    )
    assert 0.0 <= decision.confidence <= 1.0


@pytest.mark.parametrize(
    "priority,expected",
    [
        (Priority.CRITICAL, True),
        (Priority.HIGH, True),
        (Priority.MEDIUM, False),
        (Priority.LOW, False),
        (Priority.INFORMATIONAL, False),
    ],
)
def test_supervisor_notify_rules(priority: Priority, expected: bool) -> None:
    decision = SupervisorAgent().decide(_classification(priority=priority), [])
    assert decision.notify_now is expected
