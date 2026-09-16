"""Telegram authorization — allow-list of user IDs.

Only user IDs explicitly listed in `TELEGRAM_ALLOWED_USER_IDS` may interact with
HELIOS. This logic is pure (no network, no library) so it is fully testable and
is the single source of truth for access decisions (least privilege).
"""

from __future__ import annotations

from app.config import get_settings


def parse_allowed_user_ids(raw: str) -> frozenset[int]:
    """Parse a comma-separated list of user IDs into a set of ints.

    Non-numeric or empty entries are ignored defensively so a malformed config
    value can never accidentally widen access.
    """
    ids: set[int] = set()
    for chunk in raw.split(","):
        token = chunk.strip()
        if not token:
            continue
        try:
            ids.add(int(token))
        except ValueError:
            continue
    return frozenset(ids)


def get_allowed_user_ids() -> frozenset[int]:
    """Return the configured allow-list."""
    return parse_allowed_user_ids(get_settings().telegram_allowed_user_ids)


def is_authorized(user_id: int | None, allowed: frozenset[int] | None = None) -> bool:
    """Return True only if `user_id` is present in the allow-list.

    A missing user id or an empty allow-list denies access (fail closed).
    """
    if user_id is None:
        return False
    if allowed is None:
        allowed = get_allowed_user_ids()
    return user_id in allowed
