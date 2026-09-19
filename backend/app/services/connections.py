"""HELIOS COMMAND — Connection Manager (OAuth lifecycle over the registry).

Sits above the email ProviderRegistry and manages the *account connection*
lifecycle for HELIOS COMMAND: starting OAuth, handling callbacks (with CSRF
state validation), encrypting and storing tokens, listing/disconnecting, and
normalizing status. It contains no provider-specific branching in its public
API — provider differences live behind an :class:`OAuthFlow`.

Security (steering §2, §3; ADR-023/025/027)
------------------------------------------
- Every operation is scoped to the authenticated HELIOS user (anti-IDOR).
- The OAuth ``state`` is validated on callback (anti-CSRF).
- Refresh tokens are encrypted at rest (Fernet); never stored in clear, never
  returned to the frontend, never logged.
- Only read-only scopes are requested.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import AuditLog, EmailAccount, User
from app.observability import get_logger
from app.security.encryption import encrypt
from app.security.oauth_state import create_state, verify_state

logger = get_logger("app.services.connections")


class ConnectionStatus(StrEnum):
    """Provider-independent connection states surfaced to the frontend."""

    CONNECTED = "connected"
    CONNECTING = "connecting"
    EXPIRED = "expired"
    ERROR = "error"
    DISCONNECTED = "disconnected"
    REVOKED = "revoked"
    REAUTH_REQUIRED = "reauth_required"


@dataclass(frozen=True)
class ProviderMetadata:
    """Static, provider-neutral description shown by the UI."""

    provider: str
    name: str
    category: str
    capabilities: tuple[str, ...]


# Provider catalog. Adding a provider here (plus an OAuthFlow) surfaces it in the
# UI with no frontend change.
PROVIDERS: dict[str, ProviderMetadata] = {
    "gmail": ProviderMetadata(
        provider="gmail",
        name="Google Gmail",
        category="email",
        capabilities=("read_email",),
    ),
}


@dataclass(frozen=True)
class TokenResult:
    """What an OAuth flow returns after exchanging the authorization code."""

    external_account_id: str
    email_address: str
    refresh_token: str
    scopes: str
    token_expires_at: datetime | None


class OAuthFlow(Protocol):
    """Provider-specific OAuth mechanics, kept behind an interface."""

    def authorization_url(self, *, state: str, redirect_uri: str) -> str:
        """Return the provider URL to redirect the user to."""
        ...

    async def exchange_code(self, *, code: str, redirect_uri: str) -> TokenResult:
        """Exchange an authorization code for tokens + account identity."""
        ...


class ConnectionError(RuntimeError):
    """Raised when a connection operation fails (normalized for the API)."""


class ConnectionManager:
    """Manages the account connection lifecycle for one HELIOS user."""

    def __init__(self, session: Session, flows: dict[str, OAuthFlow]) -> None:
        self._session = session
        self._flows = flows

    # -- provider catalog -----------------------------------------------------

    @staticmethod
    def available_providers() -> list[ProviderMetadata]:
        return list(PROVIDERS.values())

    # -- user resolution ------------------------------------------------------

    def _get_or_create_user(self, username: str) -> User:
        """Map the HELIOS username to a User row (create on first use)."""
        stmt = select(User).where(User.external_ref == username)
        user = self._session.execute(stmt).scalar_one_or_none()
        if user is None:
            user = User(external_ref=username)
            self._session.add(user)
            self._session.flush()
        return user

    # -- OAuth start ----------------------------------------------------------

    def start_oauth(self, *, username: str, provider: str, redirect_uri: str) -> str:
        """Return the provider authorization URL for the user to visit.

        Generates a signed state bound to (user, provider) for CSRF protection.
        """
        flow = self._flow_for(provider)
        state = create_state(user=username, provider=provider)
        self._audit(username, "CONNECTION_INITIATED", {"provider": provider})
        return flow.authorization_url(state=state, redirect_uri=redirect_uri)

    # -- OAuth callback -------------------------------------------------------

    async def handle_callback(
        self, *, provider: str, code: str, state: str, redirect_uri: str
    ) -> EmailAccount:
        """Complete an OAuth flow: validate state, exchange code, store account.

        Raises :class:`ConnectionError` on CSRF/state failure or exchange error.
        """
        username = verify_state(state, provider=provider)
        if username is None:
            self._audit(None, "CONNECTION_FAILED", {"provider": provider, "reason": "bad_state"})
            raise ConnectionError("invalid or expired OAuth state")

        flow = self._flow_for(provider)
        try:
            tokens = await flow.exchange_code(code=code, redirect_uri=redirect_uri)
        except Exception as exc:  # noqa: BLE001 - normalize provider errors
            self._audit(username, "CONNECTION_FAILED", {"provider": provider})
            raise ConnectionError("failed to complete OAuth exchange") from exc

        user = self._get_or_create_user(username)
        account = self._upsert_account(user, provider, tokens)
        self._audit(
            username, "CONNECTION_COMPLETED", {"provider": provider, "account_id": account.id}
        )
        return account

    def _upsert_account(self, user: User, provider: str, tokens: TokenResult) -> EmailAccount:
        """Create or update the account row with the (encrypted) refresh token."""
        stmt = select(EmailAccount).where(
            EmailAccount.user_id == user.id,
            EmailAccount.provider == provider,
            EmailAccount.external_account_id == tokens.external_account_id,
        )
        account = self._session.execute(stmt).scalar_one_or_none()
        if account is None:
            account = EmailAccount(
                user_id=user.id,
                provider=provider,
                external_account_id=tokens.external_account_id,
            )
            self._session.add(account)

        account.email_address = tokens.email_address
        account.scopes = tokens.scopes
        # Encrypt before storage — the clear token never touches the DB.
        account.encrypted_refresh_token = encrypt(tokens.refresh_token)
        account.status = ConnectionStatus.CONNECTED.value
        account.connected_at = datetime.now(UTC)
        account.token_expires_at = tokens.token_expires_at
        account.last_error = None
        self._session.flush()
        return account

    # -- queries / disconnect (scoped to user) --------------------------------

    def list_accounts(self, username: str) -> list[EmailAccount]:
        """List the authenticated user's accounts (never other users')."""
        user = self._get_or_create_user(username)
        stmt = select(EmailAccount).where(EmailAccount.user_id == user.id)
        return list(self._session.execute(stmt).scalars().all())

    def get_account(self, username: str, account_id: int) -> EmailAccount | None:
        """Return one account only if it belongs to the user (anti-IDOR)."""
        user = self._get_or_create_user(username)
        stmt = select(EmailAccount).where(
            EmailAccount.id == account_id, EmailAccount.user_id == user.id
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def disconnect(self, username: str, account_id: int) -> bool:
        """Mark an account disconnected and drop its stored token.

        Returns False if the account does not belong to the user (no leak about
        whether the id exists at all).
        """
        account = self.get_account(username, account_id)
        if account is None:
            return False
        account.status = ConnectionStatus.DISCONNECTED.value
        account.encrypted_refresh_token = None
        self._session.flush()
        self._audit(username, "CONNECTION_DISCONNECTED", {"account_id": account_id})
        return True

    # -- helpers --------------------------------------------------------------

    def _flow_for(self, provider: str) -> OAuthFlow:
        if provider not in PROVIDERS:
            raise ConnectionError(f"unknown provider '{provider}'")
        flow = self._flows.get(provider)
        if flow is None:
            raise ConnectionError(f"no OAuth flow configured for '{provider}'")
        return flow

    def _audit(self, username: str | None, action: str, detail: dict[str, object]) -> None:
        """Record a connection audit event (never tokens)."""
        self._session.add(
            AuditLog(
                request_id=None,
                email_id=None,
                actor=f"connections:{username}" if username else "connections",
                action=action,
                detail_json=detail,
                created_at=datetime.now(UTC),
            )
        )
        self._session.flush()
