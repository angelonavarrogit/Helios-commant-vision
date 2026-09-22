// HELIOS COMMAND — API response types (mirror the backend Pydantic models).

export interface User {
  username: string;
}

export interface Provider {
  provider: string;
  name: string;
  category: string;
  capabilities: string[];
}

// Normalized connection status (matches backend ConnectionStatus). No tokens.
export type ConnectionStatus =
  | "connected"
  | "connecting"
  | "expired"
  | "error"
  | "disconnected"
  | "revoked"
  | "reauth_required";

export interface Connection {
  id: number;
  provider: string;
  email_address: string;
  status: ConnectionStatus;
  connected_at: string | null;
  last_sync_at: string | null;
  last_error: string | null;
}

export interface ConnectStart {
  authorization_url: string;
}

// Dashboard KPIs — every figure is a real DB read from the backend.
export interface DashboardKpis {
  connections_total: number;
  connections_connected: number;
  emails_total: number;
  emails_last_7d: number;
  alerts_total: number;
  alerts_sent: number;
  action_required: number;
  agent_runs_total: number;
  agent_runs_completed: number;
  category_counts: Record<string, number>;
  priority_counts: Record<string, number>;
}

export interface ActivityItem {
  id: number;
  timestamp: string;
  action: string;
  actor: string | null;
  request_id: string | null;
  email_id: number | null;
}

export interface ProviderStatus {
  provider: string;
  email: string;
  status: string;
}

export interface SystemStatus {
  core: boolean;
  database: boolean;
  connected_accounts: number;
  providers: ProviderStatus[];
}
