"""
Context-Aware Generator (CAG) Fast Cache.
In-memory SHA-256 hash cache with TTL and LRU eviction.
"""

import hashlib
import threading
import time
from collections import OrderedDict
from typing import Any, Optional

from config.logger import get_logger

logger = get_logger("memory.cag")


class CAGCache:
    """Fast in-memory cache for deterministic responses."""

    def __init__(self, max_entries: int = 500, default_ttl: int = 300):
        self.max_entries = max_entries
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._lock = threading.RLock()

    def _hash(self, text: str, extra: Optional[str] = None) -> str:
        normalized = text.strip().lower()
        if extra:
            normalized = f"{normalized}::{extra}"
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional[dict[str, Any]]:
        with self._lock:
            if key not in self._cache:
                return None
            entry = self._cache[key]
            if time.time() > entry["expires"]:
                del self._cache[key]
                return None
            self._cache.move_to_end(key)
            return entry["response"]

    def set(self, key: str, response: dict[str, Any], ttl: Optional[int] = None) -> None:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
            while len(self._cache) >= self.max_entries:
                self._cache.popitem(last=False)
            self._cache[key] = {
                "response": response,
                "expires": time.time() + (ttl or self.default_ttl),
            }

    def compute_hash(self, text: str, extra: Optional[str] = None) -> str:
        return self._hash(text, extra)

    def invalidate(self, pattern: Optional[str] = None) -> int:
        with self._lock:
            if pattern is None:
                count = len(self._cache)
                self._cache.clear()
                return count
            keys = [k for k in self._cache if pattern in k]
            for k in keys:
                del self._cache[k]
            return len(keys)

    @property
    def size(self) -> int:
        return len(self._cache)


cag_cache = CAGCache()
