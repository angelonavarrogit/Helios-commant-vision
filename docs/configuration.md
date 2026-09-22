# ⚙️ HELIOS — Configuration Reference (Phase 2)

> Single source of truth for how HELIOS is configured across environments.
> Analysis + documentation for stabilization Phase 2. Behavior-changing edits
> (splitting URLs, changing insecure defaults, binding n8n) are proposed as
> **DECISION REQUIRED** and are NOT applied in this phase.

All configuration is environment-based (12-factor). Settings load via
`app/config.py` (`Settings`, pydantic-settings) from `.env`. Secrets are never
hardcoded; only `.env.example` (placeholders) is committed.

---

## 1. Settings inventory

Grouped by concern. "Env var" is case-insensitive (pydantic `case_sensitive=false`).

### App
| Env var | Default | Notes |
|---|---|---|
| `APP_ENV` | `local` | `local` \| `prod`. In `prod`: session cookie `Secure`, docs hidden. |
| `APP_NAME` | `helios` | |
| `LOG_LEVEL` | `INFO` | `DEBUG`/`INFO`/`WARNING`/`ERROR` |
| `API_HOST` | `0.0.0.0` | Binds inside the container (intended). |
| `API_PORT` | `8000` | Host mapping via compose `${API_PORT:-8000}:8000`. |

### Database
| Env var | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `mysql+pymysql://app:changeme@mysql:3306/aipic` | ⚠ contains `changeme`. |
| `MYSQL_ROOT_PASSWORD` | `changeme-root` | compose-only. ⚠ |
| `MYSQL_DATABASE` | `aipic` | |
| `MYSQL_USER` | `app` | |
| `MYSQL_PASSWORD` | `changeme` | must match `DATABASE_URL`. ⚠ |

### LLM
| Env var | Default | Notes |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | `ollama` \| `openai` |
| `OLLAMA_URL` | `http://ollama:11434` | internal Docker DNS |
| `OLLAMA_MODEL` | `llama3.1` | |
| `OPENAI_API_KEY` | (empty) | infrastructure secret |
| `OPENAI_MODEL` | `gpt-4o-mini` | |
| `LLM_MAX_CALLS_PER_HOUR` | `200` | |

### Telegram
| Env var | Default | Notes |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | (empty) | infrastructure secret |
| `TELEGRAM_ALLOWED_USER_IDS` | (empty) | comma-separated ids |

### Google OAuth
| Env var | Default | Notes |
|---|---|---|
| `GOOGLE_CLIENT_ID` | (empty) | semi-public |
| `GOOGLE_CLIENT_SECRET` | (empty) | infrastructure secret |

### Security / auth
| Env var | Default | Notes |
|---|---|---|
| `ENCRYPTION_KEY` | (empty) | Fernet key; encrypts OAuth tokens at rest |
| `SERVICE_API_TOKEN` | (empty) | m2m token for `POST /emails/process` |
| `OWNER_USERNAME` | `owner` | |
| `OWNER_PASSWORD_HASH` | (empty) | scrypt hash; wrap in single quotes in `.env` |
| `SESSION_SECRET` | (empty) | signs session cookies |
| `SESSION_TTL_SECONDS` | `28800` | 8h |

### URLs / CORS
| Env var | Default | Notes |
|---|---|---|
| `PUBLIC_BASE_URL` | `http://localhost:8000` | Builds the OAuth redirect URI. Today points at the **API**. |
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed frontend origin(s) for credentialed CORS. |
| `VITE_API_BASE_URL` | `http://localhost:8000` (example) / empty (prod same-origin) | **Build-time**; baked into the SPA. Empty = same-origin via nginx `/api` proxy. |

### Processing / poller
| Env var | Default | Notes |
|---|---|---|
| `MAX_EMAIL_BODY_CHARS` | `50000` | defensive truncation |
| `PROCESS_RATE_LIMIT_PER_MINUTE` | `120` | per account |
| `POLL_ENABLED` | `false` | poller loop on/off |
| `POLL_INTERVAL_SECONDS` | `300` | ≥ 30 |
| `POLL_MAX_MESSAGES` | `25` | 1..500 |

---

## 2. Consistency check (`.env` vs `.env.example`)

- ✅ **Key parity:** every key in `.env` exists in `.env.example` and vice versa
  (no drift at audit time).
- ✅ **Secrets not committed:** only `.env.example` is tracked.
- ⚠ **`changeme` defaults** appear for DB credentials in `.env.example`
  (`DATABASE_URL`, `MYSQL_PASSWORD`, `MYSQL_ROOT_PASSWORD`). Safe as an example,
  but see DECISION 2.

---

## 3. Environment matrix

| Setting | LOCAL | DOCKER (this repo) | STAGING (tunnel) | PRODUCTION (domain) |
|---|---|---|---|---|
| `APP_ENV` | local | local | prod | prod |
| `API_HOST`/port | localhost:8000 | container 8000 → host 8000 | same | same |
| `DATABASE_URL` host | localhost | `mysql` (service) | `mysql` | `mysql` / managed |
| `OLLAMA_URL` | localhost:11434 | `ollama` | `ollama` | `ollama` |
| `PUBLIC_BASE_URL` | http://localhost:8000 | http://localhost:8000 | https://&lt;api&gt;.trycloudflare.com | https://api.helios.&lt;domain&gt; |
| `CORS_ORIGINS` | http://localhost:5173 | http://localhost:5173 | https://&lt;frontend&gt;.trycloudflare.com | https://helios.&lt;domain&gt; |
| `VITE_API_BASE_URL` | http://localhost:8000 | http://localhost:8000 | (empty, same-origin) | (empty, same-origin) |
| Cookie `Secure` | no (http) | no | yes (https) | yes (https) |

> Note: the same-origin deployment (nginx proxies `/api` → backend) means
> `VITE_API_BASE_URL` should be **empty** whenever the frontend and API are
> served under one hostname (tunnel/production). It only needs a value for a
> split-origin local dev without the proxy.

---

## 4. How each service reads config (compose)

- `backend`, `bot`, `poller`, `mysql`, `n8n`: `env_file: .env`.
- `frontend`: build-arg `VITE_API_BASE_URL: ${VITE_API_BASE_URL-}` (empty ⇒
  same-origin). Served by nginx which proxies `/api/` → `backend:8000`.
- `API_PORT` host mapping: `${API_PORT:-8000}:8000`.

---

## 5. DECISIONS REQUIRED (not applied in Phase 2)

### DECISION 1 — Split `PUBLIC_BASE_URL` into API vs frontend URLs?
- **Decision:** should we replace the single `PUBLIC_BASE_URL` with explicit
  `PUBLIC_API_URL` and `PUBLIC_FRONTEND_URL`?
- **Current behavior:** `PUBLIC_BASE_URL` is used only to build the Google OAuth
  redirect (an API URL). The frontend origin is handled separately by
  `CORS_ORIGINS` + `VITE_API_BASE_URL`. So functionally the concern is already
  split across three vars, just not named consistently.
- **Options:**
  - **A. Rename for clarity** → `PUBLIC_API_URL` (OAuth redirect) and keep
    `CORS_ORIGINS`/`VITE_API_BASE_URL` for the frontend. Clear, but touches
    `config.py`, `connections.py`, `.env(.example)`, docs.
  - **B. Keep `PUBLIC_BASE_URL`** and just document that it means "the API's
    public base". Zero code churn.
- **Impact:** A = small refactor + migration note; B = none.
- **Recommendation (not implemented):** **B** now (document meaning), revisit A
  only if a second consumer of the API URL appears. Lowest risk.

### DECISION 2 — Harden insecure-by-default DB credentials
- **Decision:** how to prevent shipping `changeme` to a real deployment?
- **Options:**
  - **A. Keep `changeme` in `.env.example`** (clearly an example) + add a startup
    check that refuses to boot in `APP_ENV=prod` if DB password is `changeme`.
  - **B. Replace with obvious placeholders** like `__SET_A_STRONG_PASSWORD__`.
  - **C. Both.**
- **Impact:** A adds a small guard in `config.py`/startup + a test. B/C are doc-only.
- **Recommendation (not implemented):** **C** — clearer placeholders *and* a
  prod startup guard. Best safety/clarity ratio.

### DECISION 3 — Startup environment validation
- **Decision:** should the app fail fast (in `prod`) when required secrets are
  missing/empty (`SESSION_SECRET`, `ENCRYPTION_KEY`, `OWNER_PASSWORD_HASH`,
  `SERVICE_API_TOKEN`)?
- **Current:** they default to empty strings; the app can start misconfigured.
- **Recommendation (not implemented):** add a `prod`-only validation that raises
  on empty critical secrets, with tests. Prevents insecure boots.

> These are proposed only. No code changed in Phase 2 pending your approval.
