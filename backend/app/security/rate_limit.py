"""HELIOS — simple in-process rate limiter (Phase 17 hardening).

Protects endpoints (notably POST /emails/process) from bursts and abuse (threat
T-D2). This is a fixed-window counter kept in process memory: adequate for a
single self-hosted instance. A distributed limiter (Redis) is the natural
upgrade if HELIOS ever scales horizontally (PROP-005).

Pure and deterministic given a clock, so it is easy to test.
"""

from __future__ import annotations

import threading
import time


class RateLimiter:
    """Fixed-window rate limiter: at most ``max_calls`` per ``window_seconds``."""

    def __init__(self, *, max_calls: int, window_seconds: float) -> None:
        self._max = max_calls
        self._window = window_seconds
        self._lock = threading.Lock()
        # key -> (window_start, count)
        self._buckets: dict[str, tuple[float, int]] = {}

    def allow(self, key: str, *, now: float | None = None) -> bool:
        """Return True if a call for ``key`` is allowed; record it if so."""
        current = now if now is not None else time.monotonic()
        with self._lock:
            start, count = self._buckets.get(key, (current, 0))
            if current - start >= self._window:
                # Window elapsed: reset.
                start, count = current, 0
            if count >= self._max:
                return False
            self._buckets[key] = (start, count + 1)
            return True

    def reset(self) -> None:
        """Clear all counters (used in tests)."""
        with self._lock:
            self._buckets.clear()
