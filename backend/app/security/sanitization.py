"""HELIOS — Sanitization of UNTRUSTED content (security control).

Every string that originates from email (subject, body, sender…) passes through
here before it is stored or, later, placed into an LLM prompt. Sanitization does
NOT try to "make content safe to obey" — untrusted content is never obeyed. Its
jobs are narrower and concrete:

1. **Bound size** — truncate defensively so a huge email cannot exhaust memory,
   cost, or hide a payload far down the text.
2. **Neutralize control characters** — strip non-printable/control bytes that
   can corrupt logs, terminals or downstream parsing.
3. **Normalize whitespace** — collapse noisy whitespace to keep stored text and
   prompts compact.
4. **Detect injection markers** — flag (not "fix") phrases commonly used in
   prompt-injection so the pipeline can log the attempt. Detection never changes
   behavior on its own; the four-zone separation in prompts is the real defense.

This module is pure and side-effect free (except returning data), which makes it
trivially testable.
"""

from __future__ import annotations

import re
import unicodedata

# Phrases frequently seen in prompt-injection attempts. Matched case-insensitively
# as substrings. This list is a *signal generator*, not a filter: we log matches;
# we do not rely on blocking them for safety.
_INJECTION_PATTERNS: tuple[str, ...] = (
    "ignore previous instructions",
    "ignore all previous",
    "disregard previous",
    "reveal your system prompt",
    "system prompt",
    "you are now",
    "act as",
    "forget your instructions",
)

# Control characters except common whitespace (tab, newline, carriage return).
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Runs of 3+ blank lines collapse to a single blank line.
_EXCESS_BLANK_LINES_RE = re.compile(r"\n{3,}")

# Trailing spaces on each line.
_TRAILING_WS_RE = re.compile(r"[ \t]+\n")


def strip_control_chars(text: str) -> str:
    """Remove control characters (keeps tab/newline/carriage return)."""
    return _CONTROL_CHARS_RE.sub("", text)


def normalize_whitespace(text: str) -> str:
    """Normalize Unicode and collapse noisy whitespace without losing structure."""
    # NFKC folds compatibility characters (e.g. weird spaces) to canonical forms.
    normalized = unicodedata.normalize("NFKC", text)
    normalized = _TRAILING_WS_RE.sub("\n", normalized)
    normalized = _EXCESS_BLANK_LINES_RE.sub("\n\n", normalized)
    return normalized.strip()


def truncate(text: str, max_chars: int) -> tuple[str, bool]:
    """Truncate ``text`` to ``max_chars``. Returns (text, was_truncated)."""
    if max_chars <= 0 or len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


def detect_injection(text: str) -> list[str]:
    """Return the list of injection marker phrases found (empty if none).

    Used only for logging/auditing a detected attempt; it does not alter the
    decision path.
    """
    lowered = text.lower()
    return [p for p in _INJECTION_PATTERNS if p in lowered]


def sanitize(text: str | None, *, max_chars: int) -> tuple[str, bool]:
    """Full sanitization pass for a piece of untrusted text.

    Returns the cleaned text and whether it was truncated. ``None`` becomes an
    empty string so callers get consistent types.
    """
    if not text:
        return "", False
    cleaned = strip_control_chars(text)
    cleaned = normalize_whitespace(cleaned)
    cleaned, truncated = truncate(cleaned, max_chars)
    return cleaned, truncated
