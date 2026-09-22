"""HELIOS COMMAND — server-side session lifecycle (Phase 3).

Makes sessions revocable. A signed cookie proves authenticity; this service
holds the authoritative record so logout truly invalidates a session and
expired/revoked sessions are rejected even if the cookie is still presented.

No secrets are stored: the client IP and user-agent are kept only as salted
SHA-256 hashes (for audit / anomaly hints), never in clear.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.models import UserSession


def _hash(value: str | None) -> str | None:
    """Salted SHA-256 of an IP/UA string (never stored in clear). None-safe."""
    if not value:
        return None
    secret = get_settings().session_secret.encode("utf-8")
    return hashlib.sha256(secret + value.encode("utf-8")).hexdigest()


class SessionService:
    """Create, validate (touch) and revoke server-side sessions."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        session_id: str,
        username: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> UserSession:
        """Persist a new active session row keyed by the token's jti."""
        now = datetime.now(UTC)
        ttl = get_settings().session_ttl_seconds
        row = UserSession(
            id=session_id,
            username=username,
            created_at=now,
            expires_at=now + timedelta(seconds=ttl),
            last_seen_at=now,
            revoked_at=None,
            ip_hash=_hash(ip),
            user_agent_hash=_hash(user_agent),
        )
        self._session.add(row)
        self._session.flush()
        return row

    def is_active(self, session_id: str) -> bool:
        """True if the session exists, is not revoked and not expired."""
        row = self._session.get(UserSession, session_id)
        if row is None or row.revoked_at is not None:
            return False
        # Compare in UTC; stored expires_at is naive UTC from create().
        return datetime.now(UTC).replace(tzinfo=None) <= row.expires_at

    def touch(self, session_id: str) -> None:
        """Update last_seen_at for an active session (best-effort)."""
        row = self._session.get(UserSession, session_id)
        if row is not None and row.revoked_at is None:
            row.last_seen_at = datetime.now(UTC)
            self._session.flush()

    def revoke(self, session_id: str) -> None:
        """Mark a session revoked (idempotent). Logout calls this."""
        row = self._session.get(UserSession, session_id)
        if row is not None and row.revoked_at is None:
            row.revoked_at = datetime.now(UTC)
            self._session.flush()

    def revoke_all(self, username: str) -> int:
        """Revoke every active session for a user. Returns count revoked."""
        now = datetime.now(UTC)
        stmt = select(UserSession).where(
            UserSession.username == username,
            UserSession.revoked_at.is_(None),
        )
        rows = list(self._session.execute(stmt).scalars().all())
        for row in rows:
            row.revoked_at = now
        self._session.flush()
        return len(rows)
