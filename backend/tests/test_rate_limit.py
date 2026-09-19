"""Tests for the in-process rate limiter (Phase 17)."""

from __future__ import annotations

from app.security.rate_limit import RateLimiter


def test_allows_up_to_limit() -> None:
    rl = RateLimiter(max_calls=3, window_seconds=60.0)
    assert [rl.allow("k", now=0.0) for _ in range(4)] == [True, True, True, False]


def test_separate_keys_independent() -> None:
    rl = RateLimiter(max_calls=1, window_seconds=60.0)
    assert rl.allow("a", now=0.0) is True
    assert rl.allow("b", now=0.0) is True
    assert rl.allow("a", now=0.0) is False


def test_window_resets() -> None:
    rl = RateLimiter(max_calls=1, window_seconds=10.0)
    assert rl.allow("k", now=0.0) is True
    assert rl.allow("k", now=5.0) is False
    # After the window elapses, calls are allowed again.
    assert rl.allow("k", now=10.0) is True
