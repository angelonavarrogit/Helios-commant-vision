"""Health and readiness endpoints.

`/health`  — liveness: the process is up and serving requests.
`/ready`   — readiness: dependencies are configured (extended in later phases).
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import Settings, get_settings

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
async def ready() -> ReadyResponse:
    """Readiness check.

    In Phase 1 this reports basic configuration presence. Database and LLM
    connectivity checks are added in later phases.
    """
    settings: Settings = get_settings()
    checks = {
        "config": "ok",
        "llm_provider": settings.llm_provider,
    }
    return ReadyResponse(status="ok", checks=checks)
