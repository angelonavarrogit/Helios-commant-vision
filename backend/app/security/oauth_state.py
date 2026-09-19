"""HELIOS COMMAND — OAuth ``state`` signing (CSRF protection).

The OAuth ``state`` parameter defends against CSRF on the callback: HELIOS
generates it when starting the flow and verifies it when the provider redirects
back. If an attacker forges a callback, the state won't verify.

We make ``state`` a signed, expiring token binding the flow to the HELIOS user
and provider, so a callback can only complete a flow that this user actually
started. It is stateless (HMAC-signed), so no server-side store is needed.
Reuses the same signing approach as sessions but with its own short TTL.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time

from app.config import get_settings

# OAuth flows are short-lived; 10 minutes is plenty and limits replay.
_STATE_TTL_SECONDS = 600


def create_state(*, user: str, provider: str) -> str:
    """Create a signed state binding the flow to (user, provider) with expiry.

    A random nonce is included so two concurrent flows differ.
    """
    settings = get_settings()
    nonce = secrets.token_urlsafe(8)
    expiry = int(time.time()) + _STATE_TTL_SECONDS
    payload = f"{user}:{provider}:{expiry}:{nonce}"
    signature = _sign(payload, settings.session_secret)
    return f"{_b64(payload.encode())}.{signature}"


def verify_state(state: str, *, provider: str) -> str | None:
    """Return the HELIOS username if the state is valid for ``provider``.

    Rejects tampered, expired, or wrong-provider states (returns None).
    """
    settings = get_settings()
    try:
        payload_b64, signature = state.split(".", 1)
        payload = _unb64(payload_b64).decode("utf-8")
    except (ValueError, TypeError):
        return None

    if not hmac.compare_digest(signature, _sign(payload, settings.session_secret)):
        return None

    try:
        user, state_provider, expiry_str, _nonce = payload.split(":", 3)
        expiry = int(expiry_str)
    except ValueError:
        return None

    if state_provider != provider or time.time() > expiry:
        return None
    return user


def _sign(payload: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest()
    return _b64(digest)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)
