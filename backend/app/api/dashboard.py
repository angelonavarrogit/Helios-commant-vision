"""HELIOS COMMAND — dashboard endpoints (Phase V0.2, Iteration 3).

Read-only, owner-authenticated endpoints that power the HELIOS COMMAND
dashboard: real KPIs, the recent-activity feed (from audit_logs), and the system
status snapshot. No secrets are ever returned; all numbers are real DB reads.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.database.session import get_db
from app.services.dashboard_service import DashboardService
from app.services.status_service import StatusService

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


# -- response models ----------------------------------------------------------


class KpisResponse(BaseModel):
    """Real, DB-backed key figures for the dashboard."""

    connections_total: int
    connections_connected: int
    emails_total: int
    emails_last_7d: int
    alerts_total: int
    alerts_sent: int
    action_required: int
    agent_runs_total: int
    agent_runs_completed: int
    category_counts: dict[str, int]
    priority_counts: dict[str, int]


class ActivityItemResponse(BaseModel):
    id: int
    timestamp: str
    action: str
    actor: str | None = None
    request_id: str | None = None
    email_id: int | None = None


class ProviderStatus(BaseModel):
    provider: str
    email: str
    status: str


class SystemStatusResponse(BaseModel):
    core: bool
    database: bool
    connected_accounts: int
    providers: list[ProviderStatus]


# -- endpoints ----------------------------------------------------------------


@router.get("/kpis", response_model=KpisResponse)
async def get_kpis(
    _user: Annotated[str, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> KpisResponse:
    """Return real dashboard KPIs computed from the database."""
    k = DashboardService(session).kpis()
    return KpisResponse(
        connections_total=k.connections_total,
        connections_connected=k.connections_connected,
        emails_total=k.emails_total,
        emails_last_7d=k.emails_last_7d,
        alerts_total=k.alerts_total,
        alerts_sent=k.alerts_sent,
        action_required=k.action_required,
        agent_runs_total=k.agent_runs_total,
        agent_runs_completed=k.agent_runs_completed,
        category_counts=k.category_counts,
        priority_counts=k.priority_counts,
    )


@router.get("/activity", response_model=list[ActivityItemResponse])
async def get_activity(
    _user: Annotated[str, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[ActivityItemResponse]:
    """Return the most recent audit-log entries (newest first)."""
    items = DashboardService(session).activity(limit=limit)
    return [
        ActivityItemResponse(
            id=i.id,
            timestamp=i.timestamp,
            action=i.action,
            actor=i.actor,
            request_id=i.request_id,
            email_id=i.email_id,
        )
        for i in items
    ]


@router.get("/system", response_model=SystemStatusResponse)
async def get_system_status(
    _user: Annotated[str, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> SystemStatusResponse:
    """Return a real system-health snapshot (core, DB, connected accounts)."""
    snap = StatusService(session).snapshot()
    return SystemStatusResponse(
        core=snap.core,
        database=snap.database,
        connected_accounts=snap.connected_accounts,
        providers=[ProviderStatus(**p) for p in snap.providers],
    )
