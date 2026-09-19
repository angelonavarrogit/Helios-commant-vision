"""Specialized analysis agents (Finance, Insurance, Work, Security, ...).

Each agent implements the common BaseAgent contract (see docs/agents.md).
"""

from app.agents.base import AgentResult, AnalysisContext, BaseAgent, Finding
from app.agents.documents import DocumentAgent
from app.agents.finance import FinanceAgent
from app.agents.insurance import InsuranceAgent
from app.agents.orchestrator import Orchestrator
from app.agents.security import SecurityAgent
from app.agents.supervisor import SupervisorAgent, SupervisorDecision
from app.agents.work import WorkAgent

__all__ = [
    "AgentResult",
    "AnalysisContext",
    "BaseAgent",
    "DocumentAgent",
    "FinanceAgent",
    "Finding",
    "InsuranceAgent",
    "Orchestrator",
    "SecurityAgent",
    "SupervisorAgent",
    "SupervisorDecision",
    "WorkAgent",
]
