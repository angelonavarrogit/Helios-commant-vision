"""HELIOS — Masking helpers for sensitive identifiers.

Account numbers, card numbers (PAN) and similar identifiers must never be stored
or shown in full (steering §5, data-governance). These helpers reduce them to a
safe, recognizable form (e.g. ``**** 1234``). Pure functions, easy to test.
"""

from __future__ import annotations

import re

# Sequences of 8+ digits (optionally grouped by spaces/dashes) look like account
# or card numbers. We mask everything but the last 4 digits.
_LONG_NUMBER_RE = re.compile(r"(?:\d[ -]?){8,}")


def mask_number(value: str) -> str:
    """Mask a single numeric identifier, keeping only the last 4 digits.

    Non-digits are ignored when counting; the result is always ``**** NNNN``
    (or fully masked if fewer than 4 digits are present).
    """
    digits = re.sub(r"\D", "", value)
    if len(digits) < 4:
        return "****"
    return f"**** {digits[-4:]}"


def mask_numbers_in_text(text: str) -> str:
    """Replace any long digit sequences in free text with a masked form.

    Used defensively before storing/showing text that may embed a PAN or account
    number (e.g. an email body snippet).
    """

    def _repl(match: re.Match[str]) -> str:
        return mask_number(match.group(0))

    return _LONG_NUMBER_RE.sub(_repl, text)


# One-time passwords / auth codes are typically standalone 4-8 digit numbers.
# We require a word boundary on both sides so we don't clobber parts of longer
# numbers (which mask_numbers_in_text already handles) or embedded digits.
_OTP_RE = re.compile(r"\b\d{4,8}\b")


def redact_codes(text: str) -> str:
    """Redact standalone 4-8 digit codes (OTP/2FA/verification) from text.

    Security codes must never be shown in full (steering §5). This replaces them
    with a fully-redacted marker rather than a last-4 mask, because even partial
    OTP digits are sensitive. Longer numbers (PAN/account) are handled by
    mask_numbers_in_text and are not the target here.
    """
    return _OTP_RE.sub("[REDACTED_CODE]", text)


def contains_code(text: str) -> bool:
    """True if the text appears to contain a standalone 4-8 digit code."""
    return _OTP_RE.search(text) is not None
