from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from typing import Dict, List


class RateLimitExceeded(RuntimeError):
    """Raised when tool execution rate limit is exceeded."""
    pass


class RateLimiter:
    """Sliding-window rate limiter for tracking and enforcing tool execution frequencies."""

    def __init__(self, max_calls: int = 10, period_seconds: float = 60.0) -> None:
        self.max_calls = max_calls
        self.period_seconds = period_seconds
        self._history: Dict[str, List[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    def check(self, key: str) -> bool:
        """Check if executing target key exceeds rate limit.

        Raises RateLimitExceeded if limit reached. Returns True otherwise.
        """
        now = time.time()
        window_start = now - self.period_seconds
        self._history[key] = [t for t in self._history[key] if t > window_start]
        if len(self._history[key]) >= self.max_calls:
            raise RateLimitExceeded(
                f"Rate limit exceeded for '{key}' ({self.max_calls} calls per {self.period_seconds}s)"
            )
        self._history[key].append(now)
        return True

    async def check_async(self, key: str) -> bool:
        """Async variant of check protected by asyncio.Lock."""
        async with self._lock:
            return self.check(key)
