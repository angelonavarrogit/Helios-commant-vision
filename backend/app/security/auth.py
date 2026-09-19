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


def create_session_token(username: str) -> str:
    """Create a signed, expiring session token for ``username``."""
    settings = get_settings()
    expiry = int(time.time()) + settings.session_ttl_seconds
    payload = f"{username}:{expiry}"
    signature = _sign(payload, settings.session_secret)
    return f"{_b64(payload.encode())}.{signature}"


def verify_session_token(token: str) -> str | None:
    """Return the username if the token is valid and unexpired, else None."""
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
        username, expiry_str = payload.rsplit(":", 1)
        expiry = int(expiry_str)
    except ValueError:
        return None

    if time.time() > expiry:
        return None
    return username


def _sign(payload: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest()
    return _b64(digest)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)
