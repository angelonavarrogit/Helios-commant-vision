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
