"""HELIOS — email processing endpoint (service-to-service, for N8N).

N8N (or any trusted automation) calls this endpoint when a new email arrives, and
HELIOS runs the full pipeline (fetch → normalize → store → classify → agents →
supervisor → optional notify). This is the HTTP seam described in the
architecture (docs/architecture.md §3, RF-27).

Security
--------
- Protected by a shared ``SERVICE_API_TOKEN`` (not the owner session): this is a
  machine-to-machine call, not a browser one. The token is compared in constant
  time and never logged.
- The endpoint does not accept email *content* from the caller — only an account
  id and a provider message id. HELIOS fetches the real content itself
  (read-only), so a caller cannot inject arbitrary email bodies.
"""

from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.models import EmailAccount
from app.database.session import get_db
from app.email.registry import registry
from app.observability import get_logger
from app.security import decrypt
from app.security.rate_limit import RateLimiter
from app.services.pipeline import EmailPipeline
from app.services.reports import ReportService

router = APIRouter(prefix="/api/v1/emails", tags=["emails"])
logger = get_logger("app.api.emails")

# Process-wide limiter for the ingestion endpoint (Phase 17 hardening).
_process_limiter = RateLimiter(
    max_calls=get_settings().process_rate_limit_per_minute, window_seconds=60.0
)


class ProcessRequest(BaseModel):
    account_id: int
    provider_message_id: str


class ProcessResponse(BaseModel):
    request_id: str
    email_id: int | None
    created: bool
    category: str | None = None
    importance: str | None = None
    notify_now: bool = False


def require_service_token(
    x_service_token: Annotated[str | None, Header(alias="X-Service-Token")] = None,
) -> None:
    """Validate the machine-to-machine service token (constant-time)."""
    expected = get_settings().service_api_token
    provided = x_service_token or ""
    if not expected or not hmac.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid service token"
        )


def _build_provider(account: EmailAccount):  # type: ignore[no-untyped-def]
    """Construct the real provider for an account from its stored credentials.

    The refresh token is decrypted in memory only; the provider is read-only.
    """
    credentials: dict[str, object] = {}
    if account.encrypted_refresh_token:
        credentials["refresh_token"] = decrypt(account.encrypted_refresh_token)
    return registry.create(account.provider, credentials)


@router.post("/process", response_model=ProcessResponse)
async def process_email(
    payload: ProcessRequest,
    session: Annotated[Session, Depends(get_db)],
    _auth: Annotated[None, Depends(require_service_token)],
) -> ProcessResponse:
    """Process one provider message through the full HELIOS pipeline."""
    # Rate limit per account to absorb bursts / abuse (T-D2).
    if not _process_limiter.allow(f"process:{payload.account_id}"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded"
        )

    account = session.get(EmailAccount, payload.account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    provider = _build_provider(account)
    pipeline = EmailPipeline(session, provider)
    result = await pipeline.process_message(account.id, payload.provider_message_id)

    return ProcessResponse(
        request_id=result.request_id,
        email_id=result.email_id,
        created=result.created,
        category=result.classification.category.value if result.classification else None,
        importance=result.decision.importance if result.decision else None,
        notify_now=result.decision.notify_now if result.decision else False,
    )


class ReportResponse(BaseModel):
    period: str
    text: str


@router.get("/reports/{period}", response_model=ReportResponse)
async def report(
    period: str,
    session: Annotated[Session, Depends(get_db)],
    _auth: Annotated[None, Depends(require_service_token)],
) -> ReportResponse:
    """Return a daily or weekly report (service-token protected, for N8N)."""
    service = ReportService(session)
    if period == "daily":
        return ReportResponse(period=period, text=service.daily())
    if period == "weekly":
        return ReportResponse(period=period, text=service.weekly())
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown report period")
