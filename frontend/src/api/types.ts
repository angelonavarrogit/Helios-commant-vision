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
