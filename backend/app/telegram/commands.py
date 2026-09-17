"""Command definitions and pure resolution logic for the HELIOS bot.

The command handlers here are pure functions returning text; they contain no
Telegram transport code so they can be unit-tested without network or tokens.
Phase 3 ships `/start` and `/help`; intelligence commands (/resumen, /urgentes,
/finanzas, /seguros, /trabajo, /seguridad, /documentos, /pendientes, /hoy,
/semana) are wired in Phase 12.
"""

from __future__ import annotations

from dataclasses import dataclass

# Commands planned for later phases, advertised in /help so the user knows the
# roadmap. They are not yet functional.
_PLANNED_COMMANDS: tuple[tuple[str, str], ...] = (
    ("/resumen", "Resumen del día (Fase 12)"),
    ("/urgentes", "Asuntos urgentes (Fase 12)"),
    ("/finanzas", "Eventos financieros (Fase 12)"),
    ("/seguros", "Seguros y pólizas (Fase 12)"),
    ("/trabajo", "Asuntos laborales (Fase 12)"),
    ("/seguridad", "Alertas de seguridad (Fase 12)"),
    ("/documentos", "Documentos detectados (Fase 14)"),
    ("/pendientes", "Tareas pendientes (Fase 12)"),
    ("/hoy", "Actividad de hoy (Fase 12)"),
    ("/semana", "Actividad de la semana (Fase 12)"),
)


@dataclass(frozen=True)
class CommandReply:
    """A resolved reply to a command."""

    text: str


def start_reply() -> CommandReply:
    """Reply for /start."""
    return CommandReply(
        text=(
            "☀️ HELIOS activo.\n\n"
            "Soy tu centro personal de inteligencia. Observo, entiendo, priorizo "
            "y te aviso de lo importante.\n\n"
            "Usa /help para ver los comandos disponibles."
        )
    )


def help_reply() -> CommandReply:
    """Reply for /help listing available and planned commands."""
    lines = [
        "Comandos disponibles:",
        "/start — iniciar",
        "/help — esta ayuda",
        "",
        "Próximamente:",
    ]
    lines.extend(f"{cmd} — {desc}" for cmd, desc in _PLANNED_COMMANDS)
    return CommandReply(text="\n".join(lines))


def unauthorized_reply() -> CommandReply:
    """Neutral reply for non-allow-listed users (no information leaked)."""
    return CommandReply(text="Acceso no autorizado.")


def _normalize(command: str) -> str:
    """Lowercase the command word and strip an optional @botname suffix."""
    token = command.strip().split()[0].lower() if command.strip() else ""
    return token.split("@", 1)[0]


def resolve_command(command: str) -> CommandReply | None:
    """Resolve a static command (/start, /help) to a reply, or None."""
    normalized = _normalize(command)
    if normalized == "/start":
        return start_reply()
    if normalized == "/help":
        return help_reply()
    return None


# Intelligence commands map to a QueryService method name. Kept as data so the
# transport layer stays free of per-command branching.
INTELLIGENCE_COMMANDS: dict[str, str] = {
    "/resumen": "summary",
    "/urgentes": "urgent",
    "/finanzas": "finance",
    "/seguros": "insurance",
    "/trabajo": "work",
    "/seguridad": "security",
    "/pendientes": "pending",
}


def is_intelligence_command(command: str) -> bool:
    """True if the command is one of the data-backed intelligence commands."""
    return _normalize(command) in INTELLIGENCE_COMMANDS


def query_method_for(command: str) -> str | None:
    """Return the QueryService method name for an intelligence command, or None."""
    return INTELLIGENCE_COMMANDS.get(_normalize(command))
