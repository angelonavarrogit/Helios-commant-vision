"""Specialized analysis agents (Finance, Insurance, Work, Security, ...).

Each agent implements the common BaseAgent contract (see docs/agents.md).
"""

from app.agents.base import AgentResult, AnalysisContext, BaseAgent, Finding
from app.agents.finance import FinanceAgent

__all__ = [
    "AgentResult",
    "AnalysisContext",
    "BaseAgent",
    "FinanceAgent",
    "Finding",
]
