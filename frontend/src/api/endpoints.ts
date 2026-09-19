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
