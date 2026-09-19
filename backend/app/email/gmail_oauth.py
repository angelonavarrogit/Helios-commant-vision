"""HELIOS COMMAND — Gmail OAuth flow (authorization URL + code exchange).

Implements the :class:`OAuthFlow` protocol for Gmail using google-auth-oauthlib.
Requests only the read-only scope. The google libraries are imported lazily so
they are needed only when a Gmail connection is actually performed.

This module handles the *connection* (getting a refresh token via the browser
consent flow); the runtime reading of mail is done by GmailProvider.
"""

from __future__ import annotations

from datetime import UTC

from app.config import get_settings
from app.email.gmail import GMAIL_READONLY_SCOPE
from app.services.connections import TokenResult

# Google endpoints (public, not secrets).
_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
_TOKEN_URI = "https://oauth2.googleapis.com/token"  # noqa: S105 - public URL


class GmailOAuthFlow:
    """OAuth flow for connecting a Gmail account (read-only)."""

    provider = "gmail"

    def _client_config(self, redirect_uri: str) -> dict[str, object]:
        settings = get_settings()
        return {
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "auth_uri": _AUTH_URI,
                "token_uri": _TOKEN_URI,
                "redirect_uris": [redirect_uri],
            }
        }

    def authorization_url(self, *, state: str, redirect_uri: str) -> str:
        """Build the Google consent URL (offline access to get a refresh token)."""
        from google_auth_oauthlib.flow import Flow

        flow = Flow.from_client_config(
            self._client_config(redirect_uri),
            scopes=[GMAIL_READONLY_SCOPE],
            state=state,
        )
        flow.redirect_uri = redirect_uri
        url, _ = flow.authorization_url(
            access_type="offline", include_granted_scopes="true", prompt="consent"
        )
        return str(url)

    async def exchange_code(self, *, code: str, redirect_uri: str) -> TokenResult:
        """Exchange the authorization code for a refresh token + identity."""
        from google_auth_oauthlib.flow import Flow

        flow = Flow.from_client_config(
            self._client_config(redirect_uri), scopes=[GMAIL_READONLY_SCOPE]
        )
        flow.redirect_uri = redirect_uri
        flow.fetch_token(code=code)
        creds = flow.credentials

        email_address, external_id = self._identity(creds)
        expires_at = creds.expiry.replace(tzinfo=UTC) if getattr(creds, "expiry", None) else None
        return TokenResult(
            external_account_id=external_id,
            email_address=email_address,
            refresh_token=creds.refresh_token or "",
            scopes=" ".join(creds.scopes or [GMAIL_READONLY_SCOPE]),
            token_expires_at=expires_at,
        )

    @staticmethod
    def _identity(creds: object) -> tuple[str, str]:
        """Fetch the account email + stable id via the userinfo endpoint."""
        from googleapiclient.discovery import build

        service = build("oauth2", "v2", credentials=creds, cache_discovery=False)
        info = service.userinfo().get().execute()
        return info.get("email", ""), str(info.get("id", info.get("email", "")))
