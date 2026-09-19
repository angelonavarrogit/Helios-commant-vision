"""HELIOS COMMAND — connection endpoints (auth-protected, user-scoped).

Exposes the provider catalog and the OAuth connection lifecycle to the frontend.
Every endpoint requires an authenticated HELIOS user and scopes all data to that
user (anti-IDOR). Tokens are never returned; only safe, normalized status.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.config import get_settings
from app.database.models import EmailAccount
from app.database.session import get_db
from app.email.gmail_oauth import GmailOAuthFlow
from app.services.connections import (
    ConnectionError as ConnError,
)
from app.services.connections import (
    ConnectionManager,
    OAuthFlow,
)

router = APIRouter(prefix="/api/v1/connections", tags=["connections"])


# -- response models ----------------------------------------------------------


class ProviderInfo(BaseModel):
    provider: str
    name: str
    category: str
    capabilities: list[str]


class ConnectionInfo(BaseModel):
    """Safe, user-facing view of a connected account. No tokens ever."""

    id: int
    provider: str
    email_address: str
    status: str
    connected_at: str | None = None
    last_sync_at: str | None = None
    last_error: str | None = None


class ConnectStartResponse(BaseModel):
    authorization_url: str


def _flows() -> dict[str, OAuthFlow]:
    """Registered OAuth flows. Gmail today; add providers here later."""
    return {"gmail": GmailOAuthFlow()}


def _manager(session: Session) -> ConnectionManager:
    return ConnectionManager(session, _flows())


def _to_info(account: EmailAccount) -> ConnectionInfo:
    return ConnectionInfo(
        id=account.id,
        provider=account.provider,
        email_address=account.email_address,
        status=account.status,
        connected_at=account.connected_at.isoformat() if account.connected_at else None,
        last_sync_at=account.last_sync_at.isoformat() if account.last_sync_at else None,
        last_error=account.last_error,
    )


# -- endpoints ----------------------------------------------------------------


@router.get("/providers", response_model=list[ProviderInfo])
async def list_providers(
    _user: Annotated[str, Depends(get_current_user)],
) -> list[ProviderInfo]:
    """List providers HELIOS can connect (metadata for the UI)."""
    return [
        ProviderInfo(
            provider=p.provider, name=p.name, category=p.category, capabilities=list(p.capabilities)
        )
        for p in ConnectionManager.available_providers()
    ]


@router.get("", response_model=list[ConnectionInfo])
async def list_connections(
    user: Annotated[str, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> list[ConnectionInfo]:
    """List the authenticated user's connected accounts."""
    accounts = _manager(session).list_accounts(user)
    return [_to_info(a) for a in accounts]


@router.post("/{provider}/connect", response_model=ConnectStartResponse)
async def connect(
    provider: str,
    user: Annotated[str, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> ConnectStartResponse:
    """Start an OAuth flow; returns the provider authorization URL."""
    settings = get_settings()
    redirect_uri = f"{settings.public_base_url}/api/v1/connections/{provider}/callback"
    try:
        url = _manager(session).start_oauth(
            username=user, provider=provider, redirect_uri=redirect_uri
        )
        session.commit()
    except ConnError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ConnectStartResponse(authorization_url=url)


@router.get("/{provider}/callback")
async def callback(
    provider: str,
    session: Annotated[Session, Depends(get_db)],
    code: Annotated[str, Query()],
    state: Annotated[str, Query()],
) -> RedirectResponse:
    """OAuth callback: validate state, exchange code, store the connection.

    No auth dependency here (the browser arrives from the provider), but the
    signed ``state`` binds the flow to the user who started it (anti-CSRF). On
    success/failure we redirect back to the frontend connections page.
    """
    settings = get_settings()
    redirect_uri = f"{settings.public_base_url}/api/v1/connections/{provider}/callback"
    frontend = f"{settings.public_base_url}/connections"
    try:
        await _manager(session).handle_callback(
            provider=provider, code=code, state=state, redirect_uri=redirect_uri
        )
        session.commit()
    except ConnError:
        # Never leak details; the UI shows a friendly reconnect message.
        return RedirectResponse(url=f"{frontend}?status=error", status_code=302)
    return RedirectResponse(url=f"{frontend}?status=connected", status_code=302)


@router.post("/{account_id}/disconnect")
async def disconnect(
    account_id: int,
    user: Annotated[str, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    """Disconnect an account owned by the authenticated user."""
    ok = _manager(session).disconnect(user, account_id)
    session.commit()
    if not ok:
        # 404 whether it doesn't exist or isn't yours — no existence oracle.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return {"status": "disconnected"}
