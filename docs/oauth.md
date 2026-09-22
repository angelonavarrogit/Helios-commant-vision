# 🔌 HELIOS — OAuth & Connection Manager (Phase 4)

> Audit-confirmed state of the OAuth implementation. No architecture was changed
> in Phase 4; this document captures what exists, what was verified, and the one
> known edge-case to monitor.

---

## Architecture

```
Browser                  Backend                  Google
  │                         │                        │
  │── POST /connect ────────▶│                        │
  │                    create_state(user,provider)    │
  │◀── authorization_url ───│                        │
  │                         │                        │
  │──────────────────────────────────────────────────▶│  consent
  │◀──────────── GET /callback?code=…&state=… ───────│
  │                         │                        │
  │          verify_state() ─ CSRF check              │
  │          exchange_code() ─ get refresh token      │
  │          encrypt(refresh_token) → DB               │
  │◀── redirect /connections?status=connected ────────│
```

The frontend **never** sees a token. The backend fetches and stores only.

---

## Security properties (verified)

### CSRF protection via signed state

`create_state(user, provider)` produces an HMAC-SHA256-signed token:

```
base64(user:provider:expiry:nonce).signature
```

- Bound to `(user, provider)` — a state for Gmail cannot complete an Outlook flow.
- Expires in **10 minutes** — limits replay window.
- Includes a random **nonce** — two concurrent flows never share a state.
- Signed with `SESSION_SECRET` — tamper-evident.

`verify_state(state, provider=...)` on the callback returns the username only if
all checks pass. A forged or wrong-provider state returns `None` and writes a
`CONNECTION_FAILED` audit entry.

### Token storage

- Refresh token is **encrypted at rest** (Fernet, key = `ENCRYPTION_KEY`).
- Decrypted only in memory when the provider needs it.
- **Never** stored in clear, returned to the frontend, or written to logs.
- The `detail_json` in audit entries never contains token material (tested).

### IDOR prevention

Every account access goes through:
```python
get_account(username, account_id)
# → SELECT … WHERE id=? AND user_id=?
```
A different user asking for an account they don't own gets `None`. The API
returns 404 without leaking whether the ID exists.

### Scope discipline

Only `https://www.googleapis.com/auth/gmail.readonly` is requested. No write,
send, or delete scopes are ever passed to Google.

### Callback endpoint (no auth cookie)

`GET /api/v1/connections/{provider}/callback` intentionally has **no session
dependency** — the browser arrives from Google, not from the HELIOS frontend.
The signed `state` provides the identity binding. The endpoint is not in the
CORS configuration (it does not need to be — it is a direct browser GET, not a
fetch from the SPA).

---

## Audit events written

| Event | When |
|---|---|
| `CONNECTION_INITIATED` | `POST /connect` — user starts the OAuth flow |
| `CONNECTION_COMPLETED` | Successful callback — account stored |
| `CONNECTION_FAILED` | Bad state, or token exchange error |
| `CONNECTION_DISCONNECTED` | User explicitly disconnects |

All entries use `actor = "connections:<username>"` (or `"connections"` if no
user is available). No token material appears in `detail_json`.

---

## Connection states

```
(new)  →  CONNECTING  →  CONNECTED
                        ↓         ↓
                      EXPIRED    DISCONNECTED
                        ↓
                  REAUTH_REQUIRED
                        ↓
                      REVOKED
                        ↓
                      ERROR
```

The `upsert_account` path always lands on `CONNECTED` after a successful
callback. Status transitions to `EXPIRED`/`REAUTH_REQUIRED`/`ERROR` are set by
the poller or future watch layer when token operations fail.

---

## Known edge-case (low risk, monitored)

**Google may omit `refresh_token` on re-authorization** if the user has already
consented and `prompt=consent` is not sent. This is mitigated: `authorization_url`
always includes `prompt=consent` and `access_type=offline`. If a re-connection
returns an empty refresh token, `GmailOAuthFlow.exchange_code` stores `""`, and
the next pipeline run will fail to decrypt/use it — the account should be
disconnected and reconnected. This edge case is low-risk because `prompt=consent`
forces Google to issue a new refresh token every time.

---

## Adding a new provider

1. Implement `OAuthFlow` protocol in `backend/app/email/<provider>_oauth.py`.
2. Add a `ProviderMetadata` entry to `PROVIDERS` in `connections.py` (service).
3. Register the flow in `_flows()` in `connections.py` (API).
4. No other files change — the `ConnectionManager` is provider-agnostic.

See `docs/email-providers.md` for the `EmailProvider` contract (runtime read).
