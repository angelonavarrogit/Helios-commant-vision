"""HELIOS COMMAND — authentication primitives (owner login + signed sessions).

HELIOS is self-hosted and single-owner, so authentication is intentionally
minimal but real (ADR-025): a single owner account plus a signed, expiring
session cookie. This exists to establish *who the HELIOS user is* before any
connection endpoint runs, preventing IDOR (one user touching another's accounts).

Choices
-------
- **Password hashing:** stdlib ``hashlib.scrypt`` (memory-hard KDF). We store only
  ``scrypt$salt$hash`` — never the plaintext. No third-party dependency needed.
- **Session token:** an HMAC-SHA256-signed payload of ``username:expiry``. It is
  stateless (no server session store), tamper-evident, and expires. The signing
  key is ``SESSION_SECRET`` from the environment.

None of these values are ever logged.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time

from app.config import get_settings

_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_DK_LEN = 32


def hash_password(password: str) -> str:
    """Return a ``scrypt$salt$hash`` string for a password (setup helper)."""
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_DK_LEN
    )
    return f"scrypt${_b64(salt)}${_b64(dk)}"


def verify_password(password: str, stored: str) -> bool:
    """Verify a password against a stored ``scrypt$salt$hash`` (constant-time)."""
    try:
        scheme, salt_b64, hash_b64 = stored.split("$", 2)
    except ValueError:
        return False
    if scheme != "scrypt":
        return False
    try:
        salt = _unb64(salt_b64)
        expected = _unb64(hash_b64)
    except (ValueError, TypeError):
        return False
    dk = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_DK_LEN
    )
    return hmac.compare_digest(dk, expected)


def new_session_id() -> str:
    """Return a fresh opaque session id (jti) for a server-side session row."""
    return secrets.token_urlsafe(24)


def create_session_token(username: str, session_id: str | None = None) -> str:
    """Create a signed, expiring session token for ``username``.

    The token embeds an opaque session id (``jti``) so the server can look up a
    revocable :class:`UserSession` row. ``session_id`` is generated if omitted;
    callers that persist a session should pass the id they stored.

    Payload layout is ``username:jti:expiry``. ``username`` may not contain ':'
    (owner usernames don't), so parsing is unambiguous via rsplit.
    """
    settings = get_settings()
    jti = session_id or new_session_id()
    expiry = int(time.time()) + settings.session_ttl_seconds
    payload = f"{username}:{jti}:{expiry}"
    signature = _sign(payload, settings.session_secret)
    return f"{_b64(payload.encode())}.{signature}"


def _parse_token(token: str) -> tuple[str, str, int] | None:
    """Verify signature+expiry and return ``(username, jti, expiry)`` or None.

    This is the stateless half: it proves the token is authentic and unexpired.
    Revocation (the stateful half) is checked separately against the DB.
    """
    settings = get_settings()
    try:
        payload_b64, signature = token.split(".", 1)
        payload = _unb64(payload_b64).decode("utf-8")
    except (ValueError, TypeError):
        return None

    expected_sig = _sign(payload, settings.session_secret)
    if not hmac.compare_digest(signature, expected_sig):
        return None

    try:
        username, jti, expiry_str = payload.rsplit(":", 2)
        expiry = int(expiry_str)
    except ValueError:
        return None

    if time.time() > expiry:
        return None
    return username, jti, expiry


def verify_session_token_full(token: str) -> tuple[str, str] | None:
    """Return ``(username, jti)`` if the token is authentic and unexpired."""
    parsed = _parse_token(token)
    if parsed is None:
        return None
    username, jti, _expiry = parsed
    return username, jti


def verify_session_token(token: str) -> str | None:
    """Return the username if the token is valid and unexpired, else None.

    Backward-compatible helper (stateless check only). New code should use
    :func:`verify_session_token_full` plus a DB revocation check.
    """
    parsed = _parse_token(token)
    return parsed[0] if parsed else None


def _sign(payload: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest()
    return _b64(digest)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)
