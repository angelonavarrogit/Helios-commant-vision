"""HELIOS — Email ingestion pipeline (Fetch → Parse → Normalize → Store → Classify).

This service orchestrates the core flow for a single message. It is the concrete
implementation of the data flow in docs/architecture.md §3, for Phase 5:

    provider.fetch_message(id)      # Fetch (read-only)
      → normalize(raw)              # Parse + Normalize (sanitized, hashed)
      → repository.store_normalized # Store (idempotent)
      → engine.classify(...)        # Classify (rules now; +LLM in Phase 6)
      → repository.save_classification
      → audit_log                   # why/what, for traceability

Design choices
--------------
- **Idempotent**: if the message already exists for the account, we stop early
  and report ``created=False`` so no duplicate work or alerts happen.
- **Observable**: every run carries a ``request_id`` and emits structured logs;
  each meaningful step is written to ``audit_logs`` so we can later answer
  "why did I get this alert?".
- **Fail-isolated**: agents/supervisor/notification are NOT called here yet
  (Phases 7-12). This keeps Phase 5 focused on getting a clean, stored, classified
  email — the foundation everything else builds on.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.agents.orchestrator import Orchestrator
from app.agents.supervisor import SupervisorAgent, SupervisorDecision
from app.classification.base import Classification
from app.classification.engine import ClassificationEngine
from app.database.models import AuditLog
from app.database.repositories.email_repository import EmailRepository
from app.email.base import EmailProvider
from app.email.normalizer import NormalizedEmail, normalize
from app.observability import get_logger

logger = get_logger("app.services.pipeline")


@dataclass(frozen=True)
class PipelineResult:
    """Outcome of processing a single message.

    ``created`` is False when the message was a duplicate (idempotent no-op).
    ``classification`` and ``decision`` are present only when the email was
    newly stored and analyzed.
    """

    request_id: str
    email_id: int | None
    created: bool
    classification: Classification | None
    decision: SupervisorDecision | None = None


class EmailPipeline:
    """Processes one message end-to-end (Phases 5-11)."""

    def __init__(
        self,
        session: Session,
        provider: EmailProvider,
        engine: ClassificationEngine | None = None,
        orchestrator: Orchestrator | None = None,
        supervisor: SupervisorAgent | None = None,
    ) -> None:
        self._session = session
        self._provider = provider
        self._repo = EmailRepository(session)
        self._engine = engine or ClassificationEngine()
        self._orchestrator = orchestrator or Orchestrator()
        self._supervisor = supervisor or SupervisorAgent()

    async def process_message(self, account_id: int, provider_message_id: str) -> PipelineResult:
        """Run the full pipeline for one provider message id."""
        request_id = uuid.uuid4().hex
        log_ctx = {
            "request_id": request_id,
            "account_id": account_id,
            "provider_message_id": provider_message_id,
        }
        logger.info("pipeline_start", extra=log_ctx)

        # --- Idempotency gate: skip if we already have this message ----------
        if self._repo.exists(account_id, provider_message_id):
            logger.info("pipeline_duplicate_skip", extra=log_ctx)
            self._audit(
                request_id, None, "duplicate_skip", {"provider_message_id": provider_message_id}
            )
            existing = self._repo.get_by_provider_id(account_id, provider_message_id)
            return PipelineResult(
                request_id=request_id,
                email_id=existing.id if existing else None,
                created=False,
                classification=None,
            )

        # --- Fetch (read-only) ----------------------------------------------
        raw = await self._provider.fetch_message(provider_message_id)

        # --- Parse + Normalize (sanitized, hashed) --------------------------
        normalized: NormalizedEmail = normalize(raw)
        if normalized.injection_markers:
            # Log the detected attempt for audit; behavior does not change.
            logger.warning(
                "pipeline_injection_markers_detected",
                extra={**log_ctx, "markers": normalized.injection_markers},
            )

        # --- Store (idempotent) ---------------------------------------------
        email_row, created = self._repo.store_normalized(account_id, normalized)
        if not created:
            # Race: another run stored it between our check and insert.
            logger.info("pipeline_duplicate_after_store", extra=log_ctx)
            return PipelineResult(request_id, email_row.id, False, None)

        self._audit(
            request_id,
            email_row.id,
            "email_stored",
            {
                "content_hash": normalized.content_hash,
                "body_truncated": normalized.body_truncated,
                "injection_markers": normalized.injection_markers,
            },
        )

        # --- Classify (hybrid: rules first, LLM when unsure) ----------------
        classification = await self._engine.classify(normalized)
        self._repo.save_classification(email_row.id, classification)
        self._repo.mark_processed(email_row)
        self._audit(
            request_id,
            email_row.id,
            "email_classified",
            {
                "category": classification.category.value,
                "priority": classification.priority.value,
                "method": classification.method.value,
                "confidence": classification.confidence,
            },
        )

        # --- Analyze (agents) → Consolidate (supervisor) --------------------
        run = self._repo.create_agent_run(email_row.id, request_id)
        agent_results = await self._orchestrator.run(normalized, classification)
        self._repo.save_agent_results(run.id, agent_results)
        decision = self._supervisor.decide(classification, agent_results)
        self._repo.save_supervisor_decision(run.id, decision)
        self._repo.finish_agent_run(run)
        self._audit(
            request_id,
            email_row.id,
            "supervisor_decision",
            {
                "agents_run": [r.agent_name for r in agent_results],
                "importance": decision.importance,
                "notify_now": decision.notify_now,
                # summary/reason are already masked/redacted by the agents.
                "reason": decision.reason,
            },
        )

        self._session.commit()
        logger.info(
            "pipeline_done",
            extra={
                **log_ctx,
                "email_id": email_row.id,
                "category": classification.category.value,
                "importance": decision.importance,
                "notify_now": decision.notify_now,
            },
        )
        return PipelineResult(request_id, email_row.id, True, classification, decision)

    def _audit(
        self, request_id: str, email_id: int | None, action: str, detail: dict[str, object]
    ) -> None:
        """Write an audit record. Never includes secrets (see steering §6)."""
        self._session.add(
            AuditLog(
                request_id=request_id,
                email_id=email_id,
                actor="pipeline",
                action=action,
                detail_json=detail,
                created_at=datetime.now(UTC),
            )
        )
        self._session.flush()
