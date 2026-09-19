"""ORM models — normalized data model (see docs/architecture.md §7).

Design notes:
- Portable types only (String/Text/Numeric/Boolean/DateTime/JSON) so the exact
  same models run on MySQL (prod) and SQLite (tests).
- Category/priority/etc. are stored as short strings; their allowed values are
  enforced at the application layer (Pydantic) for cross-DB portability.
- Security: no passwords/CVV/PIN/full PAN/tokens/secrets are stored. Sensitive
  identifiers are masked or hashed (see docs/data-governance.md).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_ref: Mapped[str | None] = mapped_column(String(255), unique=True)

    accounts: Mapped[list[EmailAccount]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class EmailAccount(Base, TimestampMixin):
    __tablename__ = "email_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(32))  # gmail | outlook
    email_address: Mapped[str] = mapped_column(String(320))
    # Provider's stable account id (the email can change; this id does not).
    external_account_id: Mapped[str | None] = mapped_column(String(255))
    # Reference to encrypted OAuth material (never stored in clear).
    oauth_ref: Mapped[str | None] = mapped_column(String(255))
    # Encrypted refresh token (Fernet ciphertext). Never stored in clear.
    encrypted_refresh_token: Mapped[str | None] = mapped_column(Text)
    scopes: Mapped[str | None] = mapped_column(String(512))
    # Normalized connection status (enforced at the app layer):
    # connected | connecting | expired | error | disconnected | revoked | reauth_required
    status: Mapped[str] = mapped_column(String(32), default="disconnected")
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime)
    connected_at: Mapped[datetime | None] = mapped_column(DateTime)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(String(512))

    user: Mapped[User] = relationship(back_populates="accounts")
    emails: Mapped[list[Email]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )

    # A user may hold several accounts per provider, uniquely keyed by the
    # provider's external account id (supports multi-account, multi-user).
    __table_args__ = (UniqueConstraint("user_id", "provider", "external_account_id"),)


class Institution(Base, TimestampMixin):
    __tablename__ = "institutions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[str | None] = mapped_column(String(64))  # bank | insurer | ...
    domain: Mapped[str | None] = mapped_column(String(255), index=True)


class Email(Base, TimestampMixin):
    __tablename__ = "emails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("email_accounts.id", ondelete="CASCADE"))
    provider_message_id: Mapped[str] = mapped_column(String(255))
    thread_id: Mapped[str | None] = mapped_column(String(255), index=True)
    sender: Mapped[str | None] = mapped_column(String(320))
    recipient: Mapped[str | None] = mapped_column(String(320))
    subject: Mapped[str | None] = mapped_column(String(998))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    received_at: Mapped[datetime | None] = mapped_column(DateTime)
    # UNTRUSTED content. Truncated defensively before storage/LLM.
    body_text: Mapped[str | None] = mapped_column(Text)
    snippet: Mapped[str | None] = mapped_column(String(512))
    content_hash: Mapped[str] = mapped_column(String(64), index=True)  # sha256 hex
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False)

    account: Mapped[EmailAccount] = relationship(back_populates="emails")
    attachments: Mapped[list[EmailAttachment]] = relationship(
        back_populates="email", cascade="all, delete-orphan"
    )
    labels: Mapped[list[EmailLabel]] = relationship(
        back_populates="email", cascade="all, delete-orphan"
    )
    classification: Mapped[Classification | None] = relationship(
        back_populates="email", cascade="all, delete-orphan", uselist=False
    )

    # Idempotency: a provider message is unique per account (dedupe).
    __table_args__ = (UniqueConstraint("account_id", "provider_message_id"),)


class EmailAttachment(Base, TimestampMixin):
    __tablename__ = "email_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email_id: Mapped[int] = mapped_column(ForeignKey("emails.id", ondelete="CASCADE"))
    filename: Mapped[str | None] = mapped_column(String(512))
    mime_type: Mapped[str | None] = mapped_column(String(128))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    storage_ref: Mapped[str | None] = mapped_column(String(512))
    sha256: Mapped[str | None] = mapped_column(String(64))

    email: Mapped[Email] = relationship(back_populates="attachments")


class EmailLabel(Base):
    __tablename__ = "email_labels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email_id: Mapped[int] = mapped_column(ForeignKey("emails.id", ondelete="CASCADE"))
    label: Mapped[str] = mapped_column(String(128))

    email: Mapped[Email] = relationship(back_populates="labels")


class Classification(Base, TimestampMixin):
    __tablename__ = "classifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email_id: Mapped[int] = mapped_column(ForeignKey("emails.id", ondelete="CASCADE"))
    category: Mapped[str] = mapped_column(String(32))
    subcategory: Mapped[str | None] = mapped_column(String(64))
    priority: Mapped[str] = mapped_column(String(16))
    risk_level: Mapped[str] = mapped_column(String(16))
    requires_action: Mapped[bool] = mapped_column(Boolean, default=False)
    deadline: Mapped[datetime | None] = mapped_column(DateTime)
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3))
    method: Mapped[str] = mapped_column(String(16))  # rules | llm

    email: Mapped[Email] = relationship(back_populates="classification")


class FinancialEvent(Base, TimestampMixin):
    __tablename__ = "financial_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email_id: Mapped[int] = mapped_column(ForeignKey("emails.id", ondelete="CASCADE"))
    institution_id: Mapped[int | None] = mapped_column(
        ForeignKey("institutions.id", ondelete="SET NULL")
    )
    event_type: Mapped[str] = mapped_column(String(64))
    amount: Mapped[float | None] = mapped_column(Numeric(18, 2))
    currency: Mapped[str | None] = mapped_column(String(8))
    masked_account: Mapped[str | None] = mapped_column(String(32))  # e.g. **** 1234
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)


class InsuranceEvent(Base, TimestampMixin):
    __tablename__ = "insurance_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email_id: Mapped[int] = mapped_column(ForeignKey("emails.id", ondelete="CASCADE"))
    institution_id: Mapped[int | None] = mapped_column(
        ForeignKey("institutions.id", ondelete="SET NULL")
    )
    policy_ref_masked: Mapped[str | None] = mapped_column(String(64))
    event_type: Mapped[str] = mapped_column(String(64))
    due_date: Mapped[datetime | None] = mapped_column(DateTime)
    coverage_change: Mapped[str | None] = mapped_column(Text)


class WorkEvent(Base, TimestampMixin):
    __tablename__ = "work_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email_id: Mapped[int] = mapped_column(ForeignKey("emails.id", ondelete="CASCADE"))
    event_type: Mapped[str] = mapped_column(String(64))
    requires_reply: Mapped[bool] = mapped_column(Boolean, default=False)
    deadline: Mapped[datetime | None] = mapped_column(DateTime)
    meeting_at: Mapped[datetime | None] = mapped_column(DateTime)


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email_id: Mapped[int | None] = mapped_column(ForeignKey("emails.id", ondelete="SET NULL"))
    doc_type: Mapped[str | None] = mapped_column(String(64))
    storage_ref: Mapped[str | None] = mapped_column(String(512))
    sha256: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="pending")


class Task(Base, TimestampMixin):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_email_id: Mapped[int | None] = mapped_column(
        ForeignKey("emails.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(512))
    due_date: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(32), default="open")


class Alert(Base, TimestampMixin):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email_id: Mapped[int | None] = mapped_column(ForeignKey("emails.id", ondelete="SET NULL"))
    channel: Mapped[str] = mapped_column(String(32), default="telegram")
    priority: Mapped[str] = mapped_column(String(16))
    dedupe_key: Mapped[str | None] = mapped_column(String(255), index=True)
    group_id: Mapped[str | None] = mapped_column(String(255), index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(32), default="pending")


class AgentRun(Base, TimestampMixin):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email_id: Mapped[int] = mapped_column(ForeignKey("emails.id", ondelete="CASCADE"))
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(32), default="running")

    results: Mapped[list[AgentResult]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    supervisor_decision: Mapped[SupervisorDecision | None] = relationship(
        back_populates="run", cascade="all, delete-orphan", uselist=False
    )


class AgentResult(Base, TimestampMixin):
    __tablename__ = "agent_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"))
    agent_name: Mapped[str] = mapped_column(String(64))
    output_json: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3))

    run: Mapped[AgentRun] = relationship(back_populates="results")


class SupervisorDecision(Base, TimestampMixin):
    __tablename__ = "supervisor_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"))
    importance: Mapped[str] = mapped_column(String(16))
    notify_now: Mapped[bool] = mapped_column(Boolean, default=False)
    summary: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    recommended_action: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3))

    run: Mapped[AgentRun] = relationship(back_populates="supervisor_decision")


class LLMRequest(Base, TimestampMixin):
    __tablename__ = "llm_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str | None] = mapped_column(String(128))
    tokens_prompt: Mapped[int | None] = mapped_column(Integer)
    tokens_completion: Mapped[int | None] = mapped_column(Integer)
    cost_estimate: Mapped[float | None] = mapped_column(Numeric(12, 6))
    # Hash of the prompt only — never the prompt content itself.
    prompt_hash: Mapped[str | None] = mapped_column(String(64))


class AppSetting(Base, TimestampMixin):
    """Key/value store for runtime-configurable settings (Phase 5.8).

    Secret values (tokens, API keys, password hash) are stored ENCRYPTED at rest
    (Fernet); ``is_secret`` marks them so the API never returns their content.
    DB values take precedence over `.env` for Class-B secrets (see docs).
    """

    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), unique=True)
    # Fernet ciphertext for secrets; plain text for non-secret settings.
    value: Mapped[str] = mapped_column(Text)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str | None] = mapped_column(String(64), index=True)
    email_id: Mapped[int | None] = mapped_column(ForeignKey("emails.id", ondelete="SET NULL"))
    actor: Mapped[str | None] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(128))
    detail_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
