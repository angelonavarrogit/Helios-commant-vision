"""HELIOS agents — shared date extraction (deadlines / due dates).

Several agents need to pull a date out of free email text: insurance due dates,
work deadlines, etc. This module centralizes that logic so it is written and
tested once.

It recognizes the common formats HELIOS is likely to see:
- ISO: ``2026-03-05``
- Numeric: ``05/03/2026`` and ``5-3-2026`` (day-first, the common non-US form)
- English long: ``March 5, 2026`` / ``5 March 2026``
- Spanish long: ``5 de marzo de 2026``

All parsing is defensive: unrecognized or impossible dates return ``None`` rather
than raising, because the input is untrusted email content.
"""

from __future__ import annotations

import re
from datetime import date, datetime

# Month name → number, English and Spanish (lowercased, no accents variance).
_MONTHS: dict[str, int] = {
    # English
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
    # Spanish
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

_ISO_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
# Day-first numeric (dd/mm/yyyy or d-m-yyyy). We assume day-first (non-US), which
# matches most of the world; ambiguous cases are documented as a known tradeoff.
_NUMERIC_RE = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b")
_EN_LONG_RE = re.compile(
    r"\b(?:(\d{1,2})\s+([a-z]+)|([a-z]+)\s+(\d{1,2}))(?:,)?\s+(\d{4})\b", re.IGNORECASE
)
_ES_LONG_RE = re.compile(r"\b(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})\b", re.IGNORECASE)


def _safe_date(year: int, month: int, day: int) -> datetime | None:
    """Build a datetime or return None if the components are not a real date."""
    try:
        return datetime(year, month, day)
    except ValueError:
        return None


def extract_due_date(text: str) -> datetime | None:
    """Return the first parseable date found in ``text``, or None.

    Formats are tried most-specific first (ISO, Spanish long, English long,
    numeric) so a clearly-typed date wins over an ambiguous numeric one.
    """
    if not text:
        return None

    iso = _ISO_RE.search(text)
    if iso:
        found = _safe_date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        if found:
            return found

    es = _ES_LONG_RE.search(text)
    if es:
        month = _MONTHS.get(es.group(2).lower())
        if month:
            found = _safe_date(int(es.group(3)), month, int(es.group(1)))
            if found:
                return found

    en = _EN_LONG_RE.search(text)
    if en:
        # Either "5 March 2026" (groups 1,2) or "March 5 2026" (groups 3,4).
        if en.group(1) and en.group(2):
            day, month_name = int(en.group(1)), en.group(2)
        else:
            day, month_name = int(en.group(4)), en.group(3)
        month = _MONTHS.get(month_name.lower())
        if month:
            found = _safe_date(int(en.group(5)), month, day)
            if found:
                return found

    num = _NUMERIC_RE.search(text)
    if num:
        # Day-first assumption.
        found = _safe_date(int(num.group(3)), int(num.group(2)), int(num.group(1)))
        if found:
            return found

    return None


def is_future(dt: datetime, *, reference: date | None = None) -> bool:
    """True if ``dt`` is on or after the reference date (today by default)."""
    ref = reference or datetime.now().date()
    return dt.date() >= ref
