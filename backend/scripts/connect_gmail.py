"""Connect a Gmail account from a refresh token obtained via oauth_google.py.

Reads the refresh token from the HELIOS_GMAIL_REFRESH_TOKEN environment variable
(never a CLI argument, so it does not land in shell history) and the account
email from HELIOS_GMAIL_EMAIL. Encrypts the token at rest and stores the account
for the owner user.

Usage (PowerShell), from the project root, values kept in your shell only:
    $env:HELIOS_GMAIL_REFRESH_TOKEN = "1//0g...."
    $env:HELIOS_GMAIL_EMAIL = "you@gmail.com"
    docker compose exec -e HELIOS_GMAIL_REFRESH_TOKEN -e HELIOS_GMAIL_EMAIL \
        backend python scripts/connect_gmail.py
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from pathlib import Path

# Ensure the app package is importable regardless of the working directory
# (the script lives in /app/scripts but 'app' is at /app/app).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.database.models import EmailAccount, User  # noqa: E402
from app.database.session import get_sessionmaker  # noqa: E402
from app.security.encryption import encrypt  # noqa: E402
from sqlalchemy import select  # noqa: E402


def main() -> int:
    refresh_token = os.environ.get("HELIOS_GMAIL_REFRESH_TOKEN", "").strip()
    email_address = os.environ.get("HELIOS_GMAIL_EMAIL", "").strip()
    if not refresh_token:
        print("HELIOS_GMAIL_REFRESH_TOKEN is not set.")
        return 1
    if not email_address:
        print("HELIOS_GMAIL_EMAIL is not set.")
        return 1

    settings = get_settings()
    owner = settings.owner_username
    session = get_sessionmaker()()
    try:
        user = session.execute(select(User).where(User.external_ref == owner)).scalar_one_or_none()
        if user is None:
            user = User(external_ref=owner)
            session.add(user)
            session.flush()

        # Use the email as the external account id for this setup path.
        account = session.execute(
            select(EmailAccount).where(
                EmailAccount.user_id == user.id,
                EmailAccount.provider == "gmail",
                EmailAccount.external_account_id == email_address,
            )
        ).scalar_one_or_none()
        if account is None:
            account = EmailAccount(
                user_id=user.id,
                provider="gmail",
                external_account_id=email_address,
            )
            session.add(account)

        account.email_address = email_address
        account.encrypted_refresh_token = encrypt(refresh_token)
        account.scopes = "https://www.googleapis.com/auth/gmail.readonly"
        account.status = "connected"
        account.connected_at = datetime.now(UTC)
        account.last_error = None
        session.commit()

        print(f"connected account_id={account.id} email={email_address} status=connected")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
