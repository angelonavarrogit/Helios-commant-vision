"""Tests for the database schema creation and connectivity (Phase 2)."""

from __future__ import annotations

from sqlalchemy import Engine, inspect, text
from sqlalchemy.orm import Session

# All 18 tables expected in the normalized schema (docs/architecture.md §7).
EXPECTED_TABLES = {
    "users",
    "email_accounts",
    "institutions",
    "emails",
    "email_attachments",
    "email_labels",
    "classifications",
    "financial_events",
    "insurance_events",
    "work_events",
    "documents",
    "tasks",
    "alerts",
    "agent_runs",
    "agent_results",
    "supervisor_decisions",
    "llm_requests",
    "audit_logs",
}


def test_all_tables_created(db_engine: Engine) -> None:
    tables = set(inspect(db_engine).get_table_names())
    missing = EXPECTED_TABLES - tables
    assert not missing, f"missing tables: {missing}"


def test_trivial_query_runs(db_session: Session) -> None:
    result = db_session.execute(text("SELECT 1")).scalar_one()
    assert result == 1
