// HELIOS COMMAND — endpoint wrappers (thin, typed).

import { api } from "./client";
import type { Connection, ConnectStart, Provider, User } from "./types";

export const authApi = {
  login: (username: string, password: string) =>
    api.post<User>("/api/v1/auth/login", { username, password }),
  logout: () => api.post<{ status: string }>("/api/v1/auth/logout"),
  me: () => api.get<User>("/api/v1/auth/me"),
};

export const connectionsApi = {
  providers: () => api.get<Provider[]>("/api/v1/connections/providers"),
  list: () => api.get<Connection[]>("/api/v1/connections"),
  connect: (provider: string) =>
    api.post<ConnectStart>(`/api/v1/connections/${provider}/connect`),
  disconnect: (id: number) =>
    api.post<{ status: string }>(`/api/v1/connections/${id}/disconnect`),
};

// Per-key configuration status (never includes secret values).
export interface SettingStatus {
  configured: boolean;
  source: "db" | "env" | "none";
  value?: string;
}

export interface TestResult {
  ok: boolean;
  detail: string;
}

export const settingsApi = {
  status: () => api.get<Record<string, SettingStatus>>("/api/v1/settings"),
  set: (key: string, value: string) =>
    api.put<{ status: string }>("/api/v1/settings", { key, value }),
  test: (provider: string) => api.post<TestResult>(`/api/v1/settings/test/${provider}`),
  changePassword: (currentPassword: string, newPassword: string) =>
    api.post<{ status: string }>("/api/v1/auth/change-password", {
      current_password: currentPassword,
      new_password: newPassword,
    }),
};
