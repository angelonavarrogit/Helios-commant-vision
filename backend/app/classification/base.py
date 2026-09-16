"""HELIOS BRAIN — Classification contracts (categories, priorities, result).

This module defines the *vocabulary* of classification: the enums and the
:class:`Classification` result object. Keeping these here (separate from any
classifier implementation) means rule-based and LLM-based classifiers produce
the exact same shape, and the pipeline/agents depend only on this contract.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class Category(StrEnum):
    """Top-level categories a message can fall into (docs/agents.md §1)."""

    FINANCE = "finance"
    INSURANCE = "insurance"
    WORK = "work"
    SECURITY = "security"
    DOCUMENTS = "documents"
    SHOPPING = "shopping"
    SUBSCRIPTIONS = "subscriptions"
    TRAVEL = "travel"
    EDUCATION = "education"
    PERSONAL = "personal"
    GOVERNMENT = "government"
    OTHER = "other"


class Priority(StrEnum):
    """Notification priority (drives the notification rules in later phases)."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ClassificationMethod(StrEnum):
    """How the classification was produced — recorded for cost/audit."""

    RULES = "rules"
    LLM = "llm"


class Classification(BaseModel):
    """The structured result of classifying one email.

    Mirrors the JSON shape in docs/agents.md so it is stable across rule-based
    and LLM-based classifiers.
    """

    category: Category
    subcategory: str | None = None
    priority: Priority
    risk_level: RiskLevel = RiskLevel.LOW
    requires_action: bool = False
    deadline: datetime | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    method: ClassificationMethod
