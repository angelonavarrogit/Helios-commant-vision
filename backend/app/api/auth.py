"""HELIOS COMMAND — authentication endpoints and the current-user dependency.

Exposes owner login/logout and a ``get_current_user`` dependency that other
routers (connections) depend on. Establishing identity here is what makes the
connection endpoints safe against IDOR: every connection query is scoped to the
authenticated owner.

The session lives in an HttpOnly, SameSite cookie so it is not readable by
JavaScript (mitigates token theft via XSS).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel

from app.config import get_settings
from app.security.auth import create_session_token, verify_password, verify_session_token

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

_SESSION_COOKIE = "helios_session"


class LoginRequest(BaseModel):
    username: str
    password: str


class MeResponse(BaseModel):
    username: str


def get_current_user(
    helios_session: Annotated[str | None, Cookie(alias=_SESSION_COOKIE)] = None,
) -> str:
    """FastAPI dependency: return the authenticated owner username or 401.

    Used by protected routers. Returns the username (identity) so downstream code
    can scope queries to this user.
    """
    username = verify_session_token(helios_session) if helios_session else None
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )
    return username


@router.post("/login", response_model=MeResponse)
async def login(payload: LoginRequest, response: Response) -> MeResponse:
    """Authenticate the owner and set a signed session cookie.

    Uses constant-time password verification and a neutral error so an attacker
    cannot distinguish "bad user" from "bad password".
    """
    settings = get_settings()
    valid = (
        payload.username == settings.owner_username
        and bool(settings.owner_password_hash)
        and verify_password(payload.password, settings.owner_password_hash)
    )
    if not valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_session_token(payload.username)
    response.set_cookie(
        key=_SESSION_COOKIE,
        value=token,
        httponly=True,  # not readable by JS
        samesite="lax",  # CSRF mitigation for the cookie
        secure=settings.is_prod,  # HTTPS-only in production
        max_age=settings.session_ttl_seconds,
    )
    return MeResponse(username=payload.username)


@router.post("/logout")
async def logout(response: Response) -> dict[str, str]:
    """Clear the session cookie."""
    response.delete_cookie(_SESSION_COOKIE)
    return {"status": "ok"}


@router.get("/me", response_model=MeResponse)
async def me(username: Annotated[str, Depends(get_current_user)]) -> MeResponse:
    """Return the current authenticated user (or 401)."""
    return MeResponse(username=username)
