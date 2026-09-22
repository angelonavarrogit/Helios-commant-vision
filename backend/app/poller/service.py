"""Poller service: one cycle = list recent mail per account and process new.

Read-only and idempotent. The provider is built from the account's stored
(encrypted) refresh token — the same way the /emails/process endpoint does it —
so no additional OAuth setup is required. The pipeline is given a Telegram
notifier so important mail triggers an alert automatically.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.orm import Session

import app.email.gmail  # noqa: F401  (import registers the "gmail" provider)
from app.database.models import EmailAccount
from app.database.session import get_sessionmaker
from app.email.base import EmailProvider, EmailProviderError
from app.email.registry import registry
from app.observability import get_logger
from app.security import decrypt
from app.services.pipeline import EmailPipeline
from app.telegram.notifications import TelegramNotifier

logger = get_logger("app.poller.service")


def _build_provider(account: EmailAccount) -> EmailProvider:
    """Build a read-only provider from the account's stored credentials.

    Mirrors app.api.emails._build_provider: the refresh token is decrypted in
    memory only; the OAuth client identity falls back to app settings.
    """
    credentials: dict[str, object] = {}
    if account.encrypted_refresh_token:
        credentials["refresh_token"] = decrypt(account.encrypted_refresh_token)
    return registry.create(account.provider, credentials)


class PollerService:
    """Runs polling cycles over all connected accounts."""

    def __init__(self, *, max_messages: int) -> None:
        self._max_messages = max_messages
        self._notifier = TelegramNotifier()

    def _connected_accounts(self, session: Session) -> list[EmailAccount]:
        stmt = select(EmailAccount).where(
            EmailAccount.status == "connected",
            EmailAccount.encrypted_refresh_token.is_not(None),
        )
        return list(session.execute(stmt).scalars().all())

    async def _process_account(self, session: Session, account: EmailAccount) -> dict[str, int]:
        """List recent messages for one account and process new ones."""
        stats = {"listed": 0, "new": 0, "skipped": 0, "errors": 0}
        try:
            provider = _build_provider(account)
        except Exception as exc:  # noqa: BLE001 - isolate one bad account
            logger.warning(
                "poll_provider_build_failed",
                extra={"account_id": account.id, "error": type(exc).__name__},
            )
            stats["errors"] += 1
            return stats

        try:
            refs = await provider.list_messages(limit=self._max_messages)
        except EmailProviderError as exc:
            logger.warning(
                "poll_list_failed",
                extra={"account_id": account.id, "error": type(exc).__name__},
            )
            stats["errors"] += 1
            return stats

        stats["listed"] = len(refs)
        pipeline = EmailPipeline(session, provider, notifier=self._notifier)
        for ref in refs:
            try:
                result = await pipeline.process_message(account.id, ref.provider_message_id)
                if result.created:
                    stats["new"] += 1
                else:
                    stats["skipped"] += 1
            except Exception as exc:  # noqa: BLE001 - never let one message stop the cycle
                logger.warning(
                    "poll_process_failed",
                    extra={"account_id": account.id, "error": type(exc).__name__},
                )
                stats["errors"] += 1
        return stats

    async def run_cycle(self) -> dict[str, int]:
        """Run a single polling cycle across all connected accounts."""
        totals = {"accounts": 0, "listed": 0, "new": 0, "skipped": 0, "errors": 0}
        session = get_sessionmaker()()
        try:
            accounts = self._connected_accounts(session)
            totals["accounts"] = len(accounts)
            logger.info("poll_cycle_start", extra={"accounts": len(accounts)})
            for account in accounts:
                s = await self._process_account(session, account)
                for k in ("listed", "new", "skipped", "errors"):
                    totals[k] += s[k]
        finally:
            session.close()
        logger.info("poll_cycle_done", extra=totals)
        return totals

    async def run_forever(self, *, interval_seconds: int) -> None:
        """Loop forever, running one cycle every ``interval_seconds``."""
        logger.info("poller_started", extra={"interval_seconds": interval_seconds})
        while True:
            try:
                await self.run_cycle()
            except Exception as exc:  # noqa: BLE001 - keep the loop alive
                logger.warning("poll_cycle_error", extra={"error": type(exc).__name__})
            await asyncio.sleep(interval_seconds)
