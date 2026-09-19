// HELIOS COMMAND — normalized connection status badge.

import type { ConnectionStatus } from "../api/types";

const LABELS: Record<ConnectionStatus, string> = {
  connected: "Conectado",
  connecting: "Conectando",
  expired: "Expirado",
  error: "Error",
  disconnected: "No conectado",
  revoked: "Revocado",
  reauth_required: "Reautorizar",
};

const COLORS: Record<ConnectionStatus, string> = {
  connected: "bg-helios-ok/20 text-helios-ok",
  connecting: "bg-helios-warn/20 text-helios-warn",
  expired: "bg-helios-warn/20 text-helios-warn",
  error: "bg-helios-danger/20 text-helios-danger",
  disconnected: "bg-helios-border text-helios-muted",
  revoked: "bg-helios-danger/20 text-helios-danger",
  reauth_required: "bg-helios-warn/20 text-helios-warn",
};

export function StatusBadge({ status }: { status: ConnectionStatus }) {
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${COLORS[status]}`}>
      {LABELS[status]}
    </span>
  );
}
