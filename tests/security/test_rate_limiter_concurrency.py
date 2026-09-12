import concurrent.futures
import pytest

from jarvis.tools.rate_limit import RateLimiter, RateLimitExceeded


def test_rate_limiter_thread_safety():
    """Verify rate limiter sliding window does not corrupt under concurrent threads."""
    limiter = RateLimiter(max_calls=50, period_seconds=60.0)
    key = "concurrent_key"

    def hit():
        try:
            return limiter.check(key)
        except RateLimitExceeded:
            return False

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(hit) for _ in range(100)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    allowed_count = sum(1 for r in results if r is True)
    denied_count = sum(1 for r in results if r is False)

    assert allowed_count == 50
    assert denied_count == 50
