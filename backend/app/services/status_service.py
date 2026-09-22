"""HELIOS — system status service (Phase V0.2).

Reports the health of HELIOS subsystems and providers for the Dashboard and the
Telegram ``/estado`` command. Everything reported here is real (checked live or
read from the DB); nothing is faked.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import EmailAccount
from app.database.session import check_connection


@dataclass
class SystemStatus:
    """Consolidated system health snapshot."""

    core: bool = True  # if this code runs, the core is up
    database: bool = False
    connected_accounts: int = 0
    providers: list[dict[str, str]] = field(default_factory=list)


class StatusService:
    """Builds a real system-status snapshot."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def snapshot(self) -> SystemStatus:
        db_ok = check_connection()
        accounts = list(self._session.execute(select(EmailAccount)).scalars().all())
        providers = [
            {"provider": a.provider, "email": a.email_address, "status": a.status} for a in accounts
        ]
        connected = self._session.execute(
            select(func.count()).select_from(EmailAccount).where(EmailAccount.status == "connected")
        ).scalar_one()
        return SystemStatus(
            core=True,
            database=db_ok,
            connected_accounts=connected,
            providers=providers,
        )

    def as_text(self) -> str:
        """Render the snapshot as a Telegram-friendly text block."""
        s = self.snapshot()
        dot = lambda ok: "🟢" if ok else "🔴"  # noqa: E731
        lines = [
            "☀️ HELIOS — Estado",
            f"{dot(s.core)} Core",
            f"{dot(s.database)} Base de datos",
            "",
            f"Cuentas conectadas: {s.connected_accounts}",
        ]
        for p in s.providers:
            mark = "🟢" if p["status"] == "connected" else "🔴"
            lines.append(f"  {mark} {p['provider']} · {p['email']} ({p['status']})")
        return "\n".join(lines)
