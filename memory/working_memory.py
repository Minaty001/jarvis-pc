"""
Working Memory — Current task context and temporary state.
Ephemeral, task-scoped, fast access.
"""

import time
from typing import Any, Optional


class WorkingMemory:
    """Stores current task context, active variables, and temporary state."""

    def __init__(self, max_entries: int = 50):
        self.max_entries = max_entries
        self._store: dict[str, Any] = {}
        self._timestamps: dict[str, float] = {}

    def set(self, key: str, value: Any) -> None:
        if len(self._store) >= self.max_entries and key not in self._store:
            oldest = min(self._timestamps, key=self._timestamps.get)
            del self._store[oldest]
            del self._timestamps[oldest]
        self._store[key] = value
        self._timestamps[key] = time.time()

    def get(self, key: str, default: Any = None) -> Any:
        return self._store.get(key, default)

    def delete(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            self._timestamps.pop(key, None)
            return True
        return False

    def clear(self) -> None:
        self._store.clear()
        self._timestamps.clear()

    def all(self) -> dict[str, Any]:
        return dict(self._store)

    def keys(self) -> list[str]:
        return list(self._store.keys())

    def search(self, query: str) -> list[dict]:
        """Search working memory by key/value content."""
        results = []
        query_lower = query.lower()
        for key, value in self._store.items():
            if query_lower in key.lower() or query_lower in str(value).lower():
                results.append({"key": key, "value": value, "timestamp": self._timestamps.get(key, 0)})
        return results

    def summarize(self) -> str:
        """Summarize current working memory contents."""
        if not self._store:
            return "Working memory is empty"
        lines = [f"- {k}: {str(v)[:100]}" for k, v in list(self._store.items())[:10]]
        return "Working memory:\n" + "\n".join(lines)


working_memory = WorkingMemory()
