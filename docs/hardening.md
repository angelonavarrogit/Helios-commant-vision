# HELIOS — Hardening (Phase 17)

> Última revisión: 2026-09-16. Estado de los controles de release.

This document tracks the security/reliability controls and their status. It is
the checklist the project uses as a release gate.

## Implemented controls

| Control | Where | Status |
|---|---|---|
| Untrusted-data boundary (email/docs never obeyed) | `security/sanitization.py`, agents, LLM zone separation | ✅ + gate test |
| Prompt-injection containment (end-to-end) | `tests/test_security_gate.py` | ✅ release gate |
| No secrets in git / logs | `.gitignore`, `secrets/`, structured logger redaction | ✅ verified per commit |
| Encryption at rest for OAuth refresh tokens | `security/encryption.py` (Fernet) | ✅ + test |
| OTP / security codes never surfaced | `security/masking.py` `redact_codes`, SecurityAgent | ✅ + test |
| Account/PAN masking | `security/masking.py` | ✅ + test |
| Owner auth (signed HttpOnly session) | `security/auth.py`, `api/auth.py` | ✅ + test |
| CSRF on OAuth (signed state) | `security/oauth_state.py` | ✅ + test |
| IDOR scoping (user-scoped queries) | `services/connections.py` | ✅ + test |
| Service-token auth for machine endpoints | `api/emails.py` | ✅ + test |
| Rate limiting on ingestion | `security/rate_limit.py` + `/emails/process` | ✅ + test |
| Parameterized SQL only (no injection) | ORM everywhere; LIKE wildcards escaped | ✅ + test |
| READ + ANALYZE + NOTIFY (no world-mutating actions) | supervisor advisory-only (ADR-020) | ✅ + gate test |
| CORS restricted to the frontend origin | `main.py` | ✅ |
| Defensive truncation / graceful degradation | normalizer, parser, document extraction | ✅ + tests |
| Pinned dependencies | `requirements.txt`, `frontend/package.json` | ✅ |

## Test suite as gate

The full suite (unit + integration + adversarial) must pass before release. The
adversarial cases (empty/HTML/huge/duplicate/corrupt inputs, unknown sender,
prompt injection, OTP redaction, wildcard escaping, CSRF/IDOR) are part of the
gate, per the security steering §8.

## Operational controls (documented; enable in deployment)

- **Backups**: periodic encrypted MySQL dumps with a tested restore
  (docs/operations.md §7). Not automated in the repo; wire in your host/N8N.
- **Rate limiting scope**: current limiter is in-process (single instance). For
  horizontal scale, move to a shared store (Redis, PROP-005).
- **HTTPS/HSTS**: terminate TLS at a reverse proxy in production; set
  `secure=True` cookies via `APP_ENV=prod`.
- **Dependency audit**: run `pip-audit` / `npm audit` in CI; watch for
  typosquatting on new deps.
- **Secret rotation**: rotate `SESSION_SECRET`, `ENCRYPTION_KEY`,
  `SERVICE_API_TOKEN`, bot token and OAuth client secret periodically; revoke
  OAuth on suspected compromise.

## Known limitations / future work

- Semantic memory (embeddings/vector store) deferred (ADR-028).
- OCR for image attachments not implemented (Phase 14 scope was text docs).
- Live end-to-end with real Gmail/Ollama requires user-provided credentials and
  a downloaded model; the code paths are exercised with fakes in tests.
