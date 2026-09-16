"""Health and readiness endpoints.

`/health`  — liveness: the process is up and serving requests.
`/ready`   — readiness: dependencies are configured (extended in later phases).
"""

from __future__ import annotations

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.database import check_connection

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    app: str
    env: str


class ReadyResponse(BaseModel):
    status: str
    checks: dict[str, str]


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness check. Returns 200 when the service is running."""
    settings: Settings = get_settings()
    return HealthResponse(status="ok", app=settings.app_name, env=settings.app_env)


@router.get("/ready", response_model=ReadyResponse)
async def ready(response: Response) -> ReadyResponse:
    """Readiness check.

    Reports configuration presence and database connectivity. Returns HTTP 503
    when a critical dependency (the database) is unreachable so orchestrators
    can gate traffic correctly.
    """
    settings: Settings = get_settings()
    db_ok = check_connection()
    checks = {
        "config": "ok",
        "llm_provider": settings.llm_provider,
        "database": "ok" if db_ok else "unavailable",
    }
    overall = "ok" if db_ok else "degraded"
    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadyResponse(status=overall, checks=checks)
