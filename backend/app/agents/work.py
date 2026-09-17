"""HELIOS WORK — Work agent (deterministic, rule-based).

Analyzes emails classified as work and produces structured findings: meetings,
deadlines, tasks, action-required items, follow-ups and general information.
Follows the same BaseAgent contract as the other agents.

Design choices
--------------
- **Deterministic.** Keyword detection + shared date extraction
  (``agents.dates``). Reliable, testable, free.
- **Reply detection.** Flags ``requires_reply`` when the email asks a question or
  uses explicit request phrases ("please reply", "let me know", "?"), so the user
  knows which emails are waiting on them.
- **Deadline/meeting aware.** Extracts a date into ``deadline`` (or ``meeting_at``
  for meetings) so time-sensitive work items surface in alerts.
- **Read-only.** Findings only; never replies or takes action.
"""

from __future__ import annotations

from app.agents.base import AgentResult, AnalysisContext, Finding
from app.agents.dates import extract_due_date
from app.email.normalizer import NormalizedEmail

# Event type keywords (ES/EN). Order: most specific/urgent first.
_EVENT_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "meeting",
        ("meeting", "reunión", "reunion", "call", "llamada", "invite", "invitación", "calendar"),
    ),
    ("deadline", ("deadline", "fecha límite", "fecha limite", "due by", "entrega", "vence")),
    (
        "action_required",
        ("action required", "acción requerida", "please review", "revisar", "approve", "aprobar"),
    ),
    ("task", ("task", "tarea", "to-do", "assignment", "asignación", "pending", "pendiente")),
    ("follow_up", ("follow up", "follow-up", "seguimiento", "reminder", "recordatorio")),
    ("request", ("request", "solicitud", "could you", "podrías", "can you", "puedes")),
)

# Signals that the email expects a reply from the user.
_REPLY_SIGNALS: tuple[str, ...] = (
    "please reply",
    "please respond",
    "let me know",
    "responde",
    "respóndeme",
    "your response",
    "tu respuesta",
    "awaiting your",
    "esperamos tu",
    "can you",
    "could you",
    "podrías",
    "puedes",
    "?",
)

# Event types that inherently warrant attention.
_ATTENTION_TYPES = frozenset({"deadline", "action_required", "request"})


class WorkAgent:
    """Detects and structures work-related events from an email."""

    name = "work"

    async def analyze(self, email: NormalizedEmail, ctx: AnalysisContext) -> AgentResult:
        """Return work findings. Never raises; empty result if none."""
        text = f"{email.subject}\n{email.body_text}"
        lowered = text.lower()

        event_type = self._detect_event_type(lowered)
        if event_type is None:
            return AgentResult(agent_name=self.name, confidence=0.0)

        requires_reply = self._requires_reply(lowered)
        when = extract_due_date(text)
        needs_review = requires_reply or event_type in _ATTENTION_TYPES

        detail: dict[str, object] = {"event_type": event_type, "requires_reply": requires_reply}
        if when is not None:
            # Meetings carry meeting_at; everything else a deadline.
            key = "meeting_at" if event_type == "meeting" else "deadline"
            detail[key] = when.date().isoformat()

        summary = self._summary(event_type, requires_reply, when is not None)

        finding = Finding(
            kind=event_type, summary=summary, detail=detail, needs_review=needs_review
        )
        return AgentResult(
            agent_name=self.name,
            findings=[finding],
            requires_action=needs_review,
            confidence=0.75,
        )

    # -- helpers --------------------------------------------------------------

    @staticmethod
    def _detect_event_type(lowered: str) -> str | None:
        for event_type, keywords in _EVENT_KEYWORDS:
            if any(k in lowered for k in keywords):
                return event_type
        return None

    @staticmethod
    def _requires_reply(lowered: str) -> bool:
        return any(sig in lowered for sig in _REPLY_SIGNALS)

    @staticmethod
    def _summary(event_type: str, requires_reply: bool, has_date: bool) -> str:
        base = f"Detected work {event_type.replace('_', ' ')}"
        if has_date:
            base += " with a date"
        extras = []
        if requires_reply:
            extras.append("requiere respuesta")
        if extras:
            base += " — " + ", ".join(extras)
        return base + "."
