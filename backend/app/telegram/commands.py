"""Command definitions and pure resolution logic for the HELIOS bot.

The command handlers here are pure functions returning text; they contain no
Telegram transport code so they can be unit-tested without network or tokens.
The /help text is user-facing: it lists real, working commands grouped by
purpose — no internal roadmap/phase jargon.
"""

from __future__ import annotations

from dataclasses import dataclass

# User-facing command catalog, grouped for /help. Every command listed here is
# functional. Keep descriptions friendly and free of internal jargon.
_HELP_GROUPS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    (
        "📊 Resúmenes",
        (
            ("/resumen", "Resumen general"),
            ("/hoy", "Lo de hoy"),
            ("/semana", "Lo de la semana"),
        ),
    ),
    (
        "🔔 Atención",
        (
            ("/urgentes", "Asuntos urgentes"),
            ("/pendientes", "Requieren tu acción"),
        ),
    ),
    (
        "🗂️ Por área",
        (
            ("/finanzas", "Movimientos y cargos"),
            ("/seguros", "Pólizas y vencimientos"),
            ("/trabajo", "Reuniones y tareas"),
            ("/seguridad", "Accesos y alertas"),
        ),
    ),
    (
        "🔎 Búsqueda",
        (("/buscar <término>", "Buscar en tu correo"),),
    ),
    (
        "⚙️ Sistema",
        (("/estado", "Salud del sistema y conexiones"),),
    ),
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
            "Soy tu centro personal de inteligencia. Observo tu correo, entiendo "
            "lo que llega, lo priorizo y te aviso de lo importante — sin ruido.\n\n"
            "Escribe /help para ver qué puedo hacer."
        )
    )


def help_reply() -> CommandReply:
    """Reply for /help — real commands grouped by purpose (no jargon)."""
    lines = ["☀️ HELIOS — ¿qué necesitas?", ""]
    for group_title, commands in _HELP_GROUPS:
        lines.append(group_title)
        lines.extend(f"  {cmd} — {desc}" for cmd, desc in commands)
        lines.append("")
    lines.append("Básicos: /start · /help")
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

# Report commands map to a ReportService method name (Phase 13).
REPORT_COMMANDS: dict[str, str] = {
    "/hoy": "daily",
    "/semana": "weekly",
}


def is_status_command(command: str) -> bool:
    """True if the command is the system-status command (/estado)."""
    return _normalize(command) == "/estado"


def is_report_command(command: str) -> bool:
    """True if the command is a daily/weekly report command."""
    return _normalize(command) in REPORT_COMMANDS


def report_method_for(command: str) -> str | None:
    """Return the ReportService method name for a report command, or None."""
    return REPORT_COMMANDS.get(_normalize(command))


def is_intelligence_command(command: str) -> bool:
    """True if the command is one of the data-backed intelligence commands."""
    return _normalize(command) in INTELLIGENCE_COMMANDS


def query_method_for(command: str) -> str | None:
    """Return the QueryService method name for an intelligence command, or None."""
    return INTELLIGENCE_COMMANDS.get(_normalize(command))
