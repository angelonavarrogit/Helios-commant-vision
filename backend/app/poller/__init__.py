"""Background email poller.

Periodically lists recent messages for each connected account and runs the
HELIOS pipeline on new ones — reusing the exact provider + pipeline path as the
POST /api/v1/emails/process endpoint, and the already-stored (encrypted) refresh
token. No new OAuth setup is needed. Duplicates are skipped by the pipeline's
idempotency gate, and alerts are pushed to Telegram for important mail.
"""
