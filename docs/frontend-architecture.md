# HELIOS COMMAND — Frontend Architecture

> Fase 5.7b. Última revisión: 2026-09-16.

The frontend is an isolated single-page app (SPA) that consumes the backend API.
It never talks to Google/Microsoft/DB directly and never handles secrets or
tokens (ADR-026).

## Stack

- React 18 + TypeScript (strict) + Vite 5 + Tailwind 3, React Router 6.
- Isolated package under `frontend/`, with its own Dockerfile (Node build →
  nginx static serve). No coupling to the Python backend.

## Structure

```text
frontend/
├── index.html
├── package.json / vite.config.ts / tsconfig.json / tailwind.config.js
├── Dockerfile / nginx.conf
└── src/
    ├── main.tsx            # router + providers
    ├── api/                # client (fetch w/ cookies), types, endpoints
    ├── auth/               # AuthContext + RequireAuth guard
    ├── components/         # Layout, StatusBadge
    └── pages/              # Login, Dashboard, Connections
```

## Authentication

- Login posts to `/api/v1/auth/login`; the backend sets an **HttpOnly** session
  cookie the JS cannot read (XSS mitigation).
- All API calls use `credentials: "include"` so the cookie travels with them.
- `AuthContext` derives identity from `/auth/me`; `RequireAuth` guards routes.
- CORS on the backend allows only the configured frontend origin, with
  credentials (no `*` wildcard).

## Connections flow (UI ↔ API)

```text
Connections page → POST /connections/{provider}/connect
  → backend returns authorization_url → browser redirects to provider
  → provider → GET /connections/{provider}/callback (backend validates state,
    exchanges code, encrypts token) → redirect back to /connections?status=...
  → page reloads the connection list
```

The UI is provider-agnostic: it renders whatever `/connections/providers`
returns, so adding Outlook needs no frontend change.

## Security notes

- No secrets, client IDs, tokens or refresh tokens in the frontend or
  localStorage.
- Error messages are neutral (never leak backend internals).
- Status values are the normalized backend set; the UI only displays them.

## Configuration

- `VITE_API_BASE_URL` points at the backend (defaults to `http://localhost:8000`).
- Dev: `npm run dev` (port 5173). Build: `npm run build`. Typecheck: `npm run typecheck`.
- Container: `docker compose up frontend` serves the built SPA on port 5173.
