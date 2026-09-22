# 🔐 HELIOS — Authentication & Session Security (Phase 3)

> Current implementation state. Kept in sync with code.

## Model: single owner, v1

HELIOS v1 has exactly one owner. The authentication goal is to establish *who
the HELIOS user is* so connection endpoints can scope queries to that owner
(anti-IDOR), and so the Telegram bot only serves allow-listed users.

Future multi-user support is architecturally prepared but not implemented.

---

## Password storage

- Algorithm: stdlib `hashlib.scrypt` (memory-hard KDF, N=2¹⁴, r=8, p=1, dklen=32).
- Storage format: `scrypt$<salt_b64>$<dk_b64>` (never the plaintext).
- Verification: constant-time `hmac.compare_digest`.
- The hash lives in `app_settings` (DB, encrypted at rest by Fernet).
  The `.env` value is the bootstrap fallback; DB takes precedence.

**Never log, return or expose the hash or password.**

---

## Session token (signed cookie)

On login, HELIOS issues a signed, expiring token embedded in an `HttpOnly`,
`SameSite=Lax`, optionally `Secure` (in prod) cookie named `helios_session`.

Token format: `base64(username:jti:expiry).hmac_sha256_signature`

- `jti` — opaque session id (random `secrets.token_urlsafe(24)`).
- `expiry` — Unix timestamp; default TTL 8 h (`SESSION_TTL_SECONDS`).
- Signature key — `SESSION_SECRET` from the environment.
- Tamper-evident: any modification invalidates the signature.
- The cookie is not readable by JavaScript (HttpOnly).

---

## Revocable sessions — `user_sessions` table (Phase 3)

The token alone proves authenticity but cannot be revoked before expiry. Phase 3
adds server-side session records:

| Column | Purpose |
|---|---|
| `id` | The token's `jti` (primary key, random) |
| `username` | Owner username (indexed) |
| `created_at` | When the session was opened |
| `expires_at` | Hard expiry (matches token TTL) |
| `last_seen_at` | Updated on each authenticated request (touch) |
| `revoked_at` | Set by logout; NULL = active |
| `ip_hash` | Salted SHA-256 of client IP (audit, never clear) |
| `user_agent_hash` | Salted SHA-256 of User-Agent (audit, never clear) |

**A session is valid iff:** token signature is valid AND `revoked_at IS NULL`
AND `now() <= expires_at`.

### What each action does

| Action | Stateless token | Server-side row |
|---|---|---|
| Login | Issued, embedded in cookie | Row created (`revoked_at=NULL`) |
| Each request | Signature + expiry verified | Row looked up; `last_seen_at` touched |
| Logout | Cookie deleted from browser | `revoked_at` set → immediately rejected |
| Change password | Token still valid (crypto) | **All rows** for this user revoked |
| Token expiry | Rejected by time check | Row stays (expires naturally) |

### Why this matters

Before Phase 3: logout only deleted the browser cookie. A stolen or intercepted
token was valid until its TTL expired (up to 8 h).

After Phase 3: logout is immediate and server-authoritative. A replayed token
after logout returns 401.

---

## Brute-force / rate limiting

Currently handled at the network level (Cloudflare) and by the constant-time
comparison in `verify_password`. A dedicated login rate-limiter is not yet
implemented — tracked as future work.

---

## What is NOT implemented in v1

- **MFA / 2FA** — documented as a future phase.
- **Session listing UI** — the DB has the data; exposing it in HELIOS COMMAND is future.
- **Concurrent session limit** — no maximum enforced yet.

---

## Relevant files

| File | Role |
|---|---|
| `backend/app/security/auth.py` | Password hashing, token create/verify |
| `backend/app/services/session_service.py` | Session create, touch, revoke, revoke_all |
| `backend/app/api/auth.py` | `/login`, `/logout`, `/me`, `/change-password` |
| `backend/app/database/models.py` | `UserSession` model |
| `backend/alembic/versions/7294bf961386_user_sessions.py` | Migration |
