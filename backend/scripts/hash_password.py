"""Generate an owner password hash for HELIOS COMMAND (setup helper).

Usage:
    python backend/scripts/hash_password.py
Then paste the printed value into OWNER_PASSWORD_HASH in your .env.
The plaintext password is never stored anywhere.
"""

from __future__ import annotations

import getpass

from app.security.auth import hash_password


def main() -> int:
    pw = getpass.getpass("Owner password: ")
    if not pw:
        print("Empty password; aborting.")
        return 1
    print("\nOWNER_PASSWORD_HASH=" + hash_password(pw))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
