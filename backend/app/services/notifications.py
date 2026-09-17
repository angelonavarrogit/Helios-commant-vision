"""HELIOS — Notification service (priority rules + dedupe, no spam).

Decides whether a supervisor decision should reach the user now and, if so,
delivers it through a :class:`Notifier` (Telegram in production, a fake in
tests). Every attempt is recorded as an ``alerts`` row so the audit can answer
"why did I get this alert?".

Anti-spam design (docs/agents.md §6)
------------------------------------
- **Priority rules.** Only decisions with ``notify_now`` (critical/high) are sent
  immediately; lower importance is stored, not pushed.
- **Deduplication.** A ``dedupe_key`` (per email + importance) prevents the same
  logical event from alerting twice; repeated events are recorded as "grouped"
  and not re-sent.

The message text comes from the supervisor summary, which is already
masked/redacted by the agents — this service never adds raw email content.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.supervisor import SupervisorDecision
from app.database.repositories.email_repository import EmailRepository
from app.observability import get_logger
from app.telegram.notifications import Notifier

logger = get_logger("app.services.notifications")

# Importance levels that warrant an immediate push.
_NOTIFY_LEVELS = frozenset({"critical", "high"})


class NotificationService:
    """Applies notification rules and delivers alerts without spamming."""

    def __init__(self, session: Session, notifier: Notifier) -> None:
        self._repo = EmailRepository(session)
        self._notifier = notifier

    def _dedupe_key(self, email_id: int | None, decision: SupervisorDecision) -> str:
        """Build a stable key for one logical alert event."""
        return f"{email_id}:{decision.importance}"

    async def maybe_notify(self, *, email_id: int | None, decision: SupervisorDecision) -> bool:
        """Send an alert if the rules say so. Returns True if a message was sent.

        - Not notify_now → store nothing extra, return False.
        - Duplicate (same dedupe key) → record as 'grouped', do not resend.
        - Otherwise → deliver and record as 'sent'.
        """
        if not decision.notify_now or decision.importance not in _NOTIFY_LEVELS:
            return False

        key = self._dedupe_key(email_id, decision)
        if self._repo.alert_exists(key):
            # Same logical event already alerted: group, don't resend (no spam).
            self._repo.create_alert(
                email_id=email_id,
                priority=decision.importance,
                dedupe_key=key,
                group_id=key,
                status="grouped",
            )
            logger.info("alert_grouped", extra={"dedupe_key": key})
            return False

        text = self._format(decision)
        sent = await self._notifier.send(text=text, priority=decision.importance)
        self._repo.create_alert(
            email_id=email_id,
            priority=decision.importance,
            dedupe_key=key,
            group_id=key,
            status="sent" if sent else "failed",
        )
        logger.info("alert_sent", extra={"dedupe_key": key, "delivered": sent})
        return sent

    @staticmethod
    def _format(decision: SupervisorDecision) -> str:
        """Build the alert text from the (already-safe) supervisor summary."""
        icon = "🔴" if decision.importance == "critical" else "🟠"
        return (
            f"{icon} HELIOS — {decision.importance.upper()}\n"
            f"{decision.summary}\n"
            f"Acción sugerida: {decision.recommended_action}"
        )
