# 📋 PROJECT HELIOS — Baseline (Phase 1 audit)

> Reference snapshot of the **real** state of PROJECT HELIOS before any
> stabilization change. This is the line against which later phases are compared.
> Audit only — nothing was fixed in this phase. Claims here are backed by
> commands run against the repo/containers, not by documentation alone.

- **Date:** 2026-09-22
- **Commit at audit:** `56db86e` (branch `main`)
- **Working tree:** clean except the new `docs/roadmap.md` and this file (both
  documentation, no code changes).

---

## 1. Repository & version state

- Branch `main`, tracking `origin/main` on GitHub
  (`angelonavarrogit/Helios-commant-vision`).
- History verified clean of secrets: only `.env.example` is tracked; no `.env`,
  tokens, `.pem`, or credential files in the tree or history.

## 2. Project structure (backend `app/`)

- **API routers (7 modules):** `auth`, `connections`, `dashboard`, `emails`,
  `health`, `settings` (+ `__init__`).
- **Email layer (`email/`):** `base`, `fake`, `gmail`, `gmail_oauth`,
  `normalizer`, `parser`, `registry`. Real provider: **Gmail only**.
- **LLM layer (`llm/`):** `base`, `fake`, `ollama`, `openai` — proper provider
  abstraction; agents are not coupled to a concrete LLM.
- **Agents (`agents/`):** `finance`, `insurance`, `work`, `security`,
  `documents`, plus `orchestrator`, `supervisor`, `dates`.
- **Background workers:** `telegram/` (bot, long-polling) and `poller/`
  (auto-processing loop).
- **Tests:** 29 `test_*.py` files.

## 3. Database & migrations

- Alembic migrations (3), head applied and up to date:
  1. `419df1184d05` — initial schema
  2. `4f5bd3329298` — email accounts connection lifecycle
  3. `3d3ab27636de` — app_settings (encrypted runtime settings)
- Current DB revision = head = `3d3ab27636de`.
- Normalized connection states already modeled: `connected`, `connecting`,
  `expired`, `error`, `disconnected`, `revoked`, `reauth_required`.

## 4. Runtime / Docker

7 services running at audit time:

| Service | State |
|---|---|
| backend | Up, healthy |
| bot (Telegram) | Up, healthy |
| poller (auto-process) | Up, healthy |
| frontend | Up |
| mysql | Up, healthy |
| n8n | Up |
| ollama | Up |

- Ollama models present: `llama3.1` (4.9 GB), `llama3.2:1b` (1.3 GB).
- MySQL has **no host port** (internal `backnet` only). n8n is published on
  `5678` (see risks).

## 5. Quality gate (measured, not assumed)

- **Backend:** `pytest` → **230 passed**; `ruff` clean; `black --check` clean;
  `mypy app` clean (74 source files).
- **Frontend:** `npm run build` (tsc strict + vite) → clean, 43 modules,
  bundle ≈188 KB (≈60 KB gzip).

## 6. API surface (endpoints)

- **auth:** `POST /login`, `POST /logout`, `GET /me`, `POST /change-password`
- **connections:** `GET /providers`, `GET ""`, `POST /{provider}/connect`,
  `GET /{provider}/callback`, `POST /{account_id}/disconnect`
- **dashboard:** `GET /kpis`, `GET /activity`, `GET /system`
- **emails:** `POST /process` (X-Service-Token), `GET /reports/{period}`
- **health:** `GET /health`, `GET /ready`
- **settings:** `GET ""`, `PUT ""`, `POST /test/{provider}`, `DELETE /{key}`

All owner-facing endpoints require the session cookie; `/emails/*` uses a
machine-to-machine service token.

## 7. Documentation inventory

**Present in `docs/`:** `agents`, `architecture`, `brand`, `data-governance`,
`decisions`, `email-providers`, `frontend-architecture`, `GETTING_STARTED`,
`hardening`, `helios-command`, `operations`, `PRODUCTION_CLOUDFLARE`,
`requirements`, `security`, `testing`, `threat-model`, `vision`, `roadmap` (new).

**Referenced by the roadmap but NOT present (would be created in their phases):**
`PROJECT_HELIOS.md`, `project-baseline.md` (this file, now created),
`configuration.md`, `authentication.md`, `session-security.md`,
`secrets-management.md`, `helios-watch.md`, `backup-recovery.md`,
`production-deployment.md`, `quality-gates.md`, `PROJECT_STATUS.md`,
`final-architecture-review.md`.

> Note: `PROJECT_HELIOS.md` is intentionally absent. Per `docs/vision.md` §7, the
> original file arrived as untrusted content with embedded instructions; the
> vision was re-authored as `docs/vision.md` instead.

---

## 8. Functionality status

### ✅ Confirmed (working, verified)
- **Auth:** owner login, signed session cookie (HttpOnly, SameSite=Lax, Secure in
  prod), change-password.
- **Connections / OAuth:** Gmail OAuth connect/callback/disconnect; refresh token
  encrypted at rest; frontend never receives tokens. One Gmail account connected.
- **Ingestion + pipeline:** fetch → normalize → store → classify (rules + LLM) →
  agents → supervisor → notify; idempotent (dedupe by `account_id` +
  `provider_message_id`).
- **Auto-processing (poller):** lists recent mail per connected account and runs
  the pipeline on new messages; verified live processing real Gmail and sending a
  Telegram alert for a high-priority item.
- **Telegram bot:** commands incl. `/resumen` (now an executive briefing),
  `/urgentes`, `/pendientes`, per-area, `/buscar`, `/estado`; alerts on important
  mail; OTP codes redacted in output.
- **Dashboard (HELIOS COMMAND):** real KPIs, activity feed (audit_logs), system
  status; Connections Center; secure Settings (write-only secrets + test button).
- **Secure settings:** Class-B secrets encrypted at rest (Fernet), never returned.
- **Observability:** structured JSON logs with secret redaction; `audit_logs`.
- **Deployment path:** Cloudflare Tunnel (same-origin API via nginx proxy);
  validated online (login + dashboard) end-to-end.
- **Quality gate:** green (see §5).

### 🟡 Partially implemented
- **Documents:** DocumentAgent handles text-based PDF/Excel/Word; **OCR for
  images is not implemented**.
- **Search:** keyword search over subject/body exists; **no semantic / vector
  search**.
- **Alert model:** severity via priority + supervisor `notify_now`, but **no
  explicit severity×confidence engine** (roadmap idea #3).
- **Audit visibility:** `audit_logs` populated and exposed via `/dashboard/activity`;
  **no dedicated filterable Security→Audit view** yet.
- **Multi-account / multi-provider:** schema and registry support it; only Gmail
  is wired.

### ⛔ Documented / envisioned but NOT implemented
- **Outlook provider** (roadmap Phase 18).
- **HELIOS WATCH** system-watch layer (roadmap Phase 11 / idea #2).
- **HELIOS DAILY** proactive morning briefing (idea #1).
- **HELIOS EXPLAIN, MEMORY (layered), FEEDBACK, RULE ENGINE (user-defined),
  CALENDAR, TASKS, ANALYTICS, CHAT, PROACTIVE INTELLIGENCE** (ideas #4–#21).
- **Session revocation store** (`user_sessions`).
- **Backups / restore** strategy.
- **MFA.**

---

## 9. Technical debt

1. **Sessions are not revocable.** `logout` only clears the browser cookie
   (`delete_cookie`); the signed token stays valid until expiry. No
   `user_sessions` table. → Target of stabilization Phase 3.
2. **Classification accuracy.** Observed live: marketing/travel emails (e.g.
   Airbnb) misclassified as *security* by the local LLM. Needs rule tuning /
   prompt work / feedback loop.
3. **First-run alert noise.** The poller analyzed pre-existing mail on first run,
   producing several security alerts at once. Dedupe prevents repeats, but a
   first-run/backfill strategy (and severity threshold) is missing.
4. **Frontend has no automated tests** (only tsc typecheck + build). Roadmap
   Phase 16 lists frontend lint/typecheck/build/tests.
5. **Docs vs reality drift risk.** Several roadmap-referenced docs don't exist;
   `PROJECT_STATUS.md` as a single source of truth is missing (Phase 17).
6. **`changeme` placeholders** in `.env.example` for DB — safe as an example, but
   Phase 2 should make insecure-by-default harder.

## 10. Risks

- **n8n exposed on `5678`.** Published to the host and not needed for the poller
  path. Should be bound to `127.0.0.1` or removed from the tunnel (Phase 15).
- **Temporary public URLs (trycloudflare).** Current online exposure depends on
  quick tunnels whose URLs rotate and have no uptime guarantee; not production.
- **Exposed secrets in chat history.** The Telegram bot token, Google Client
  Secret and Gmail refresh token appeared in conversation and should be rotated.
- **Owner password** is still the temporary `helios-admin`.
- **Single-owner model.** Fine for v1, but any move toward internet/multi-user
  needs the auth/session hardening first.

## 11. Recommendations (order, not executed here)

1. **Phase 2 — Configuration:** separate API vs frontend public URLs cleanly;
   validate local/docker/prod; document in `configuration.md`.
2. **Phase 3 — Sessions:** add revocable `user_sessions`; make logout truly
   invalidate. Highest-value security fix.
3. **Phase 7 — Secrets:** rotate exposed secrets; document rotation.
4. **Phase 15 — Docker hardening:** bind/close n8n; review ports.
5. Address classification accuracy via the Rule Engine + Feedback loop (product
   roadmap #15/#16) once the foundation is hardened.

---

## 12. Baseline metrics (for future comparison)

| Metric | Value at baseline |
|---|---|
| Backend tests | 230 passed |
| Backend lint/format/types | ruff ✓ · black ✓ · mypy ✓ |
| Frontend build | ✓ (43 modules) |
| Alembic migrations | 3 (head applied) |
| API routers / endpoints | 7 / 20 |
| Real email providers | 1 (Gmail) |
| LLM providers | 3 (ollama, openai, fake) |
| Specialized agents | 5 (+ orchestrator, supervisor) |
| Docker services | 7 |
