"""HELIOS SECURITY — Security agent (deterministic, rule-based).

Analyzes emails classified as security and produces structured findings: new
sign-ins, access attempts, password changes, security alerts, authentication
codes (OTP/2FA) and suspicious activity. Follows the BaseAgent contract.

Critical security rule (steering §5)
------------------------------------
This agent handles emails that frequently contain one-time codes. It must
**never** surface a full OTP/verification code. Every string it puts into a
finding (summary and detail) is passed through ``redact_codes`` so standalone
4-8 digit codes become ``[REDACTED_CODE]``. The agent still reports that a code
was present (so the user knows), just never the code itself.

Other choices
-------------
- **Deterministic** keyword detection (reliable, testable, free).
- **Suspicious activity → needs_review** and high attention, using calibrated
  language (no accusations).
- **Read-only.** Findings only; never changes credentials or takes action.
"""

from __future__ import annotations

from app.agents.base import AgentResult, AnalysisContext, Finding
from app.email.normalizer import NormalizedEmail
from app.security.masking import contains_code, redact_codes

# Event type keywords (ES/EN). Order: most sensitive/urgent first.
_EVENT_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "suspicious_activity",
        (
            "suspicious",
            "sospechosa",
            "unusual activity",
            "actividad inusual",
            "unauthorized",
            "no autorizado",
        ),
    ),
    (
        "access_attempt",
        ("sign-in attempt", "intento de acceso", "login attempt", "failed login", "acceso fallido"),
    ),
    (
        "new_sign_in",
        ("new sign-in", "nuevo inicio de sesión", "new login", "new device", "nuevo dispositivo"),
    ),
    (
        "password_change",
        (
            "password change",
            "cambio de contraseña",
            "password was reset",
            "restablecer contraseña",
            "reset your password",
        ),
    ),
    (
        "auth_code",
        (
            "verification code",
            "código de verificación",
            "one-time",
            "otp",
            "2fa",
            "security code",
            "código de seguridad",
        ),
    ),
    (
        "security_alert",
        ("security alert", "alerta de seguridad", "security notification", "aviso de seguridad"),
    ),
)

# Event types that always warrant the user's attention.
_ATTENTION_TYPES = frozenset({"suspicious_activity", "access_attempt", "password_change"})


class SecurityAgent:
    """Detects and structures security events; never surfaces full codes."""

    name = "security"

    async def analyze(self, email: NormalizedEmail, ctx: AnalysisContext) -> AgentResult:
        """Return security findings. Never raises; empty result if none."""
        text = f"{email.subject}\n{email.body_text}"
        lowered = text.lower()

        event_type = self._detect_event_type(lowered)
        if event_type is None:
            return AgentResult(agent_name=self.name, confidence=0.0)

        code_present = contains_code(text)
        needs_review = event_type in _ATTENTION_TYPES

        detail: dict[str, object] = {"event_type": event_type, "code_present": code_present}

        summary = self._summary(event_type, code_present, needs_review)

        finding = Finding(
            kind=event_type,
            summary=summary,  # already code-redacted in _summary
            detail=detail,
            needs_review=needs_review,
        )
        return AgentResult(
            agent_name=self.name,
            findings=[finding],
            requires_action=needs_review,
            confidence=0.8,
        )

    # -- helpers --------------------------------------------------------------

    @staticmethod
    def _detect_event_type(lowered: str) -> str | None:
        for event_type, keywords in _EVENT_KEYWORDS:
            if any(k in lowered for k in keywords):
                return event_type
        return None

    @staticmethod
    def _summary(event_type: str, code_present: bool, needs_review: bool) -> str:
        base = f"Detected security {event_type.replace('_', ' ')}"
        if code_present:
            # Report presence, never the code itself.
            base += " (a verification code was included and has been hidden)"
        if needs_review:
            base += " — requiere revisión."
        else:
            base += "."
        # Defensive: ensure no standalone code ever leaks into the summary text.
        return redact_codes(base)
