"""HELIOS EYE — Gmail provider (read-only OAuth).

This is the first concrete :class:`EmailProvider`. It reads mail via the
official Gmail API using OAuth with the **read-only** scope
``gmail.readonly`` — HELIOS can never modify or send mail with these
credentials (least privilege, ADR-007).

Credentials
-----------
A Gmail account is authorized once (interactively) to obtain a *refresh token*
(see ``scripts/oauth_google.py``). At runtime the provider is built from:

    - client_id / client_secret  (the OAuth app identity, from env)
    - refresh_token              (per-account, decrypted from storage)

No secret is hardcoded. The refresh token is expected to arrive already
decrypted in memory (the DB stores it encrypted — see security/encryption.py).

Lazy imports
------------
The Google client libraries are heavy and only needed when Gmail is actually
used. They are imported *inside* methods so importing this module (e.g. during
tests or app startup) never requires them and never touches the network.

Blocking I/O
------------
The Google client is synchronous. To honor the async :class:`EmailProvider`
contract without blocking the event loop, network calls run in a thread via
``asyncio.to_thread``.
"""

from __future__ import annotations

import asyncio
import base64
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from app.config import get_settings
from app.email.base import (
    EmailProvider,
    EmailProviderError,
    ProviderMessageRef,
    RawAttachment,
    RawEmail,
)
from app.observability import get_logger

logger = get_logger("app.email.gmail")

# Read-only scope. This is the single most important least-privilege control
# for email: with only this scope the token cannot send, delete or modify mail.
GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"

# Google's OAuth token endpoint (used to exchange the refresh token).
# Not a secret: this is a public, well-known URL.
_GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"  # noqa: S105


class GmailProvider(EmailProvider):
    """Read-only Gmail email source."""

    name = "gmail"

    def __init__(self, *, client_id: str, client_secret: str, refresh_token: str) -> None:
        # Basic validation so we fail fast with a clear message instead of
        # deep inside a Google client call.
        if not (client_id and client_secret and refresh_token):
            raise EmailProviderError(
                "GmailProvider requires client_id, client_secret and refresh_token"
            )
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token

    # -- credential / client construction ------------------------------------

    def _build_credentials(self) -> Any:
        """Create google-auth Credentials from the refresh token.

        Imported lazily. The access token is obtained by Google from the
        refresh token on first use; we never persist the short-lived access
        token.
        """
        from google.oauth2.credentials import Credentials

        return Credentials(
            token=None,
            refresh_token=self._refresh_token,
            client_id=self._client_id,
            client_secret=self._client_secret,
            token_uri=_GOOGLE_TOKEN_URI,
            scopes=[GMAIL_READONLY_SCOPE],
        )

    def _build_service(self) -> Any:
        """Build the Gmail API client (synchronous, hence run in a thread)."""
        from googleapiclient.discovery import build

        credentials = self._build_credentials()
        # cache_discovery=False avoids a noisy warning and file cache in containers.
        return build("gmail", "v1", credentials=credentials, cache_discovery=False)

    # -- EmailProvider contract ----------------------------------------------

    async def list_messages(self, *, limit: int = 50) -> list[ProviderMessageRef]:
        """List recent message ids from the inbox (read-only)."""
        try:
            return await asyncio.to_thread(self._list_messages_sync, limit)
        except EmailProviderError:
            raise
        except Exception as exc:  # noqa: BLE001 - normalize any client error
            logger.warning("gmail_list_failed", extra={"error": type(exc).__name__})
            raise EmailProviderError("failed to list Gmail messages") from exc

    def _list_messages_sync(self, limit: int) -> list[ProviderMessageRef]:
        service = self._build_service()
        # We do not mark anything as read; listing is a pure read.
        response = (
            service.users()
            .messages()
            .list(userId="me", maxResults=max(1, min(limit, 500)))
            .execute()
        )
        refs: list[ProviderMessageRef] = []
        for item in response.get("messages", []):
            refs.append(
                ProviderMessageRef(provider_message_id=item["id"], thread_id=item.get("threadId"))
            )
        return refs

    async def fetch_message(self, provider_message_id: str) -> RawEmail:
        """Fetch a full message and map it into a provider-neutral RawEmail."""
        try:
            return await asyncio.to_thread(self._fetch_message_sync, provider_message_id)
        except EmailProviderError:
            raise
        except Exception as exc:  # noqa: BLE001 - normalize any client error
            logger.warning(
                "gmail_fetch_failed",
                extra={"error": type(exc).__name__, "message_id": provider_message_id},
            )
            raise EmailProviderError("failed to fetch Gmail message") from exc

    def _fetch_message_sync(self, provider_message_id: str) -> RawEmail:
        service = self._build_service()
        # format="full" returns headers + body parts. We never call modify().
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=provider_message_id, format="full")
            .execute()
        )
        return self._map_message(msg)

    # -- mapping helpers ------------------------------------------------------

    @staticmethod
    def _header(headers: list[dict[str, str]], name: str) -> str | None:
        """Return a header value by (case-insensitive) name, or None."""
        lowered = name.lower()
        for header in headers:
            if header.get("name", "").lower() == lowered:
                return header.get("value")
        return None

    @classmethod
    def _map_message(cls, msg: dict[str, Any]) -> RawEmail:
        """Translate a Gmail API message dict into a RawEmail (all UNTRUSTED)."""
        payload = msg.get("payload", {})
        headers = payload.get("headers", [])

        body_text, body_html = cls._extract_bodies(payload)
        attachments = cls._extract_attachments(payload)

        # internalDate is epoch millis as a string.
        received_at: datetime | None = None
        raw_internal = msg.get("internalDate")
        if raw_internal:
            try:
                received_at = datetime.fromtimestamp(int(raw_internal) / 1000, tz=UTC)
            except (ValueError, OverflowError):
                received_at = None

        return RawEmail(
            provider="gmail",
            provider_message_id=msg.get("id", ""),
            thread_id=msg.get("threadId"),
            sender=cls._header(headers, "From"),
            recipient=cls._header(headers, "To"),
            subject=cls._header(headers, "Subject"),
            received_at=received_at,
            body_text=body_text,
            body_html=body_html,
            snippet=msg.get("snippet"),
            labels=list(msg.get("labelIds", [])),
            attachments=attachments,
        )

    @classmethod
    def _extract_bodies(cls, payload: dict[str, Any]) -> tuple[str | None, str | None]:
        """Walk MIME parts collecting the first text/plain and text/html bodies."""
        text: str | None = None
        html: str | None = None

        def walk(part: dict[str, Any]) -> None:
            nonlocal text, html
            mime = part.get("mimeType", "")
            data = part.get("body", {}).get("data")
            if data:
                decoded = cls._decode_b64url(data)
                if mime == "text/plain" and text is None:
                    text = decoded
                elif mime == "text/html" and html is None:
                    html = decoded
            for child in part.get("parts", []) or []:
                walk(child)

        walk(payload)
        return text, html

    @classmethod
    def _extract_attachments(cls, payload: dict[str, Any]) -> list[RawAttachment]:
        """Collect attachment metadata only (never the bytes)."""
        found: list[RawAttachment] = []

        def walk(part: dict[str, Any]) -> None:
            filename = part.get("filename")
            if filename:
                found.append(
                    RawAttachment(
                        filename=filename,
                        mime_type=part.get("mimeType"),
                        size_bytes=part.get("body", {}).get("size"),
                    )
                )
            for child in part.get("parts", []) or []:
                walk(child)

        walk(payload)
        return found

    @staticmethod
    def _decode_b64url(data: str) -> str | None:
        """Decode Gmail's URL-safe base64 body data to text, defensively."""
        try:
            raw = base64.urlsafe_b64decode(data.encode("ascii"))
            return raw.decode("utf-8", errors="replace")
        except (ValueError, TypeError):
            return None


def gmail_factory(credentials: Mapping[str, Any]) -> EmailProvider:
    """Registry factory for Gmail.

    Credentials keys:
        - ``refresh_token`` (required, per-account; already decrypted)
        - ``client_id`` / ``client_secret`` (optional; fall back to app env)

    Falling back to the app-level OAuth client identity means the per-account
    credential is just the refresh token, which is the only truly per-account
    secret.
    """
    settings = get_settings()
    client_id = str(credentials.get("client_id") or settings.google_client_id)
    client_secret = str(credentials.get("client_secret") or settings.google_client_secret)
    refresh_token = str(credentials.get("refresh_token") or "")
    return GmailProvider(
        client_id=client_id, client_secret=client_secret, refresh_token=refresh_token
    )


# Register Gmail on import so it is available through the shared registry.
# Imported here (bottom) to avoid a circular import at module top.
from app.email.registry import registry  # noqa: E402

registry.register("gmail", gmail_factory)
