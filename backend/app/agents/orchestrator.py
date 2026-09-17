"""HELIOS ORCHESTRATOR — selects and runs the specialized agents.

Given a classified email, the orchestrator decides which agents to run (based on
category), runs them concurrently, and collects their :class:`AgentResult`s for
the supervisor to consolidate.

Design choices
--------------
- **Category-driven selection.** A small map decides which agents apply. Some
  categories fan out to more than one agent (e.g. a "security" email may also be
  worth a work check); the default is to at least try the agent matching the
  category.
- **Concurrent + fault-isolated.** Agents run with ``asyncio.gather``; if one
  agent raises, its failure is logged and skipped — one bad agent never sinks the
  others (reliability, docs/operations.md §4).
- **No side effects.** The orchestrator neither writes to the DB nor notifies;
  it returns results for the pipeline/supervisor to handle.
"""

from __future__ import annotations

import asyncio

from app.agents.base import AgentResult, AnalysisContext, BaseAgent
from app.agents.finance import FinanceAgent
from app.agents.insurance import InsuranceAgent
from app.agents.security import SecurityAgent
from app.agents.work import WorkAgent
from app.classification.base import Category, Classification
from app.email.normalizer import NormalizedEmail
from app.observability import get_logger

logger = get_logger("app.agents.orchestrator")


def _default_agents() -> dict[str, BaseAgent]:
    """Instantiate the available agents keyed by name."""
    return {
        "finance": FinanceAgent(),
        "insurance": InsuranceAgent(),
        "work": WorkAgent(),
        "security": SecurityAgent(),
    }


# Which agent names to run for each category. Categories without a specific
# agent fall back to an empty list (the supervisor still sees the classification).
_CATEGORY_AGENTS: dict[Category, tuple[str, ...]] = {
    Category.FINANCE: ("finance",),
    Category.INSURANCE: ("insurance",),
    Category.WORK: ("work",),
    Category.SECURITY: ("security",),
}


class Orchestrator:
    """Runs the specialized agents applicable to a classified email."""

    def __init__(self, agents: dict[str, BaseAgent] | None = None) -> None:
        self._agents = agents or _default_agents()

    def select(self, classification: Classification) -> list[BaseAgent]:
        """Return the agents that apply to this classification."""
        names = _CATEGORY_AGENTS.get(classification.category, ())
        return [self._agents[n] for n in names if n in self._agents]

    async def run(
        self, email: NormalizedEmail, classification: Classification
    ) -> list[AgentResult]:
        """Run the applicable agents concurrently and return their results.

        A failing agent is logged and omitted; the rest still return.
        """
        selected = self.select(classification)
        if not selected:
            return []

        ctx = AnalysisContext(classification=classification)
        outcomes = await asyncio.gather(
            *(agent.analyze(email, ctx) for agent in selected),
            return_exceptions=True,
        )

        results: list[AgentResult] = []
        for agent, outcome in zip(selected, outcomes, strict=True):
            if isinstance(outcome, BaseException):
                logger.warning(
                    "agent_failed",
                    extra={"agent": agent.name, "error": type(outcome).__name__},
                )
                continue
            results.append(outcome)
        return results
