"""One-time interactive OAuth helper to obtain a Gmail refresh token.

Run this locally, once per Gmail account, to authorize HELIOS with the
**read-only** scope and print a refresh token you can store (encrypted) for the
provider to use later.

Usage
-----
    python backend/scripts/oauth_google.py --client-secret secrets/google_client_secret.json

What it does
------------
1. Loads the OAuth *client* credentials (client_id/secret) from the JSON you
   downloaded from Google Cloud Console.
2. Opens a browser for you to consent to the read-only Gmail scope.
3. Prints the resulting refresh token.

Security
--------
- The client-secret JSON and the printed refresh token are secrets: keep them
  out of git (the repo ignores ``secrets/`` and ``client_secret*.json``).
- Store the refresh token encrypted (see app.security.encryption). Never commit
  it and never paste it into logs.
- This script is intentionally NOT imported by the app; it is an operator tool.
"""

from __future__ import annotations

import argparse
import sys

# Only the read-only scope is ever requested (least privilege).
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Obtain a Gmail read-only refresh token.")
    parser.add_argument(
        "--client-secret",
        required=True,
        help="Path to the OAuth client secret JSON from Google Cloud Console.",
    )
    args = parser.parse_args()

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print(
            "google-auth-oauthlib is required. Install backend/requirements.txt first.",
            file=sys.stderr,
        )
        return 1

    # run_local_server spins up a temporary localhost callback and opens a
    # browser for consent. access_type=offline is required to receive a
    # refresh token; prompt=consent forces Google to return one every time.
    flow = InstalledAppFlow.from_client_secrets_file(args.client_secret, scopes=SCOPES)
    credentials = flow.run_local_server(port=0, access_type="offline", prompt="consent")

    if not credentials.refresh_token:
        print(
            "No refresh token returned. Revoke prior access and retry with a fresh consent.",
            file=sys.stderr,
        )
        return 2

    print("\n--- COPY THIS REFRESH TOKEN (store it encrypted, never in git) ---")
    print(credentials.refresh_token)
    print("--- end ---")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
