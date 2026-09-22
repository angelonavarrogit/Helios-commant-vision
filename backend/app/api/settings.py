"""HELIOS COMMAND — secure settings endpoints (Phase 5.8).

Lets the authenticated owner configure Class-B secrets (Telegram, OpenAI,
Google) from the UI. Values are encrypted at rest by the SettingsService and are
NEVER returned to the client — the status endpoint only reports whether each key
is configured and its source (db/env).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.database.session import get_db
from app.services.settings_service import MANAGED_KEYS, SettingsService

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])

# Keys settable via this endpoint (owner_password_hash is handled by auth).
_SETTABLE_KEYS = MANAGED_KEYS - {"owner_password_hash"}


class SetSettingRequest(BaseModel):
    key: str
    value: str


@router.get("")
async def get_status(
    _user: Annotated[str, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> dict[str, dict[str, object]]:
    """Return, per managed key, whether it is configured and its source.

    Never returns secret values.
    """
    return SettingsService(session).status()


@router.put("")
async def set_setting(
    payload: SetSettingRequest,
    _user: Annotated[str, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    """Store (encrypted) a managed setting value."""
    if payload.key not in _SETTABLE_KEYS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown or non-settable key"
        )
    try:
        SettingsService(session).set_secret(payload.key, payload.value)
        session.commit()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"status": "saved"}


class TestResponse(BaseModel):
    ok: bool
    detail: str


_TESTABLE_PROVIDERS = frozenset({"telegram", "openai", "ollama"})


@router.post("/test/{provider}", response_model=TestResponse)
async def test_connection(
    provider: str,
    _user: Annotated[str, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> TestResponse:
    """Verify a provider's saved credentials by calling its API.

    Returns a safe ok/detail result; never echoes the secret. Lets the user
    confirm from the Settings screen that a token/key actually works.
    """
    if provider not in _TESTABLE_PROVIDERS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown provider")
    result = await SettingsService(session).test_connection(provider)
    return TestResponse(ok=result.ok, detail=result.detail)


@router.delete("/{key}")
async def delete_setting(
    key: str,
    _user: Annotated[str, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    """Remove a stored setting (the app then falls back to `.env`)."""
    if key not in _SETTABLE_KEYS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown key")
    SettingsService(session).delete(key)
    session.commit()
    return {"status": "deleted"}
