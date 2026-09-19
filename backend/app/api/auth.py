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
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.session import get_db
from app.security.auth import (
    create_session_token,
    hash_password,
    verify_password,
    verify_session_token,
)
from app.services.settings_service import SettingsService

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
async def login(
    payload: LoginRequest,
    response: Response,
    session: Annotated[Session, Depends(get_db)],
) -> MeResponse:
    """Authenticate the owner and set a signed session cookie.

    The password hash is resolved with DB-over-env precedence, so a password
    changed from the UI (stored in app_settings) takes effect immediately while
    the `.env` value remains the initial bootstrap credential.

    Uses constant-time password verification and a neutral error so an attacker
    cannot distinguish "bad user" from "bad password".
    """
    settings = get_settings()
    effective_hash = SettingsService(session).get_effective("owner_password_hash")
    valid = (
        payload.username == settings.owner_username
        and bool(effective_hash)
        and verify_password(payload.password, effective_hash)
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


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    _username: Annotated[str, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    """Change the owner password (stored hashed in the DB, taking precedence).

    Requires a valid session AND the current password, so a stolen session alone
    cannot change the password. The new hash is stored in app_settings; the
    `.env` value stays as the bootstrap fallback.
    """
    svc = SettingsService(session)
    current_hash = svc.get_effective("owner_password_hash")
    if not current_hash or not verify_password(payload.current_password, current_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect"
        )
    if len(payload.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters",
        )
    svc.set_secret("owner_password_hash", hash_password(payload.new_password))
    session.commit()
    return {"status": "ok"}
