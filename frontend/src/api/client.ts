// HELIOS COMMAND — typed API client.
//
// All requests include credentials (the HttpOnly session cookie) so the browser
// authenticates without the frontend ever handling tokens. The base URL comes
// from VITE_API_BASE_URL; no secrets are stored here.

// API base URL. In production the SPA is served behind a reverse proxy that
// forwards "/api/..." to the backend on the same origin, so the base is empty
// (relative URLs). For local dev without a proxy, set VITE_API_BASE_URL to the
// backend origin (e.g. http://localhost:8000). An empty/undefined value means
// same-origin, which is the safe production default.
const RAW_BASE = import.meta.env.VITE_API_BASE_URL;
const BASE_URL = RAW_BASE && RAW_BASE.trim() !== "" ? RAW_BASE : "";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    credentials: "include", // send/receive the session cookie
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
  });

  if (!response.ok) {
    // Never surface backend internals; keep a short, safe message.
    let detail = `Request failed (${response.status})`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body?.detail) detail = body.detail;
    } catch {
      // ignore non-JSON error bodies
    }
    throw new ApiError(response.status, detail);
  }

  // Some endpoints return no body (204/redirects handled elsewhere).
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PUT", body: body ? JSON.stringify(body) : undefined }),
  baseUrl: BASE_URL,
};
