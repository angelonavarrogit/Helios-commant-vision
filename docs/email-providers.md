# HELIOS EYE — Email Providers (architecture & how to add one)

> Última revisión: 2026-09-16.

HELIOS is designed to ingest mail from **multiple accounts and multiple provider
types**. Gmail is the first implementation; Outlook, IMAP and others can be added
without touching the pipeline. This document explains the design and the exact
steps to add a new provider.

## 1. The contract

Everything lives behind `app/email/base.py`:

- `EmailProvider` (Protocol): `name`, `list_messages(limit)`, `fetch_message(id)`.
  Read-only by design — there is no send/delete/modify method.
- `RawEmail`, `ProviderMessageRef`, `RawAttachment`: provider-neutral data
  objects. Each provider maps its native payload into these shapes.
- `EmailProviderError`: single error type all providers raise, so the pipeline
  handles failures uniformly (retry / dead-letter / log).

Downstream code (normalizer, classifier, agents) depends **only** on these
abstractions — never on a concrete provider.

## 2. The registry

`app/email/registry.py` holds a map of `name -> factory`. A factory builds a
provider instance from a per-account credentials mapping. This keeps
credentials out of global state and lets each account carry its own token.

```text
registry.register("gmail", gmail_factory)
provider = registry.create("gmail", {"refresh_token": "<decrypted>"})
```

Concrete providers register themselves on import (see the bottom of
`gmail.py`). The shared instance is `app.email.registry.registry`.

## 3. Security rules for any provider

- **Read-only scope only.** Request the minimum scope (`gmail.readonly` for
  Gmail). Never request write/send scopes.
- **No secrets in code or git.** OAuth client identity comes from env
  (`GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`). The per-account refresh token
  is stored **encrypted** (see `app/security/encryption.py`) and only decrypted
  in memory.
- **Everything returned is UNTRUSTED.** Never let subject/body/sender act as
  instructions.
- **Don't mutate the mailbox.** No "mark as read".
- **Don't block the event loop.** If the SDK is synchronous, wrap calls in
  `asyncio.to_thread` (see Gmail).

## 4. How to add a provider (e.g. Outlook)

1. Create `app/email/outlook.py` with `class OutlookProvider(EmailProvider)`:
   - set `name = "outlook"`,
   - implement `list_messages` and `fetch_message`,
   - map the Microsoft Graph payload into `RawEmail`,
   - request the read-only Mail scope only,
   - wrap network errors in `EmailProviderError`.
2. Add an `outlook_factory(credentials)` that builds it (falling back to env for
   the app client identity, like Gmail).
3. Register it: `registry.register("outlook", outlook_factory)` at import time.
4. Add a `Fake*` path in tests if the mapping is non-trivial; reuse
   `FakeEmailProvider` for pipeline tests.
5. Store the account with `email_accounts.provider = "outlook"`.

No pipeline, classifier or agent code changes are required.

## 5. Testing

- Unit-test the payload → `RawEmail` mapping with fixtures (no network).
- Use `FakeEmailProvider` to exercise the pipeline deterministically.
- Include adversarial fixtures: empty body, HTML-only, huge body, unknown
  sender, missing headers.

## 6. Obtaining Gmail credentials (operator step)

1. Create an OAuth client (Desktop app) in Google Cloud Console; download the
   client-secret JSON into `secrets/` (git-ignored).
2. Run once:

   ```bash
   python backend/scripts/oauth_google.py --client-secret secrets/google_client_secret.json
   ```

3. Store the printed refresh token **encrypted** for the account; put
   `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` in your `.env`.
