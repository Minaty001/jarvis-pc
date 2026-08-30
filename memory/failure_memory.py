"""
Failure Memory — Past failures, causes, fixes, and recovery strategies.
Learns from mistakes to avoid repeating them.
"""

import time
import uuid
from typing import Any, Optional


class FailureMemory:
    """Stores failures and their recovery strategies."""

    def __init__(self, max_entries: int = 500):
        self.max_entries = max_entries
        self._failures: list[dict] = []

    def remember(
        self,
        action: str,
        error: str,
        cause: str = "",
        fix: str = "",
        context: Optional[dict] = None,
    ) -> str:
        """Store a failure and its resolution."""
        failure_id = f"fail-{str(uuid.uuid4())[:8]}"
        failure = {
            "id": failure_id,
            "action": action,
            "error": error,
            "cause": cause,
            "fix": fix,
            "context": context or {},
            "created_at": time.time(),
            "occurrence_count": 1,
            "last_occurrence": time.time(),
        }
        self._failures.append(failure)

        if len(self._failures) > self.max_entries:
            self._failures.sort(key=lambda f: f["occurrence_count"])
            self._failures = self._failures[-self.max_entries:]

        return failure_id

    def retrieve(
        self,
        action: str = "",
        error: str = "",
        limit: int = 5,
    ) -> list[dict]:
        """Find similar past failures."""
        candidates = self._failures

        if action:
            action_lower = action.lower()
            candidates = [f for f in candidates if action_lower in f["action"].lower()]

        if error:
            error_lower = error.lower()
            candidates = [f for f in candidates if error_lower in f["error"].lower()]

        if action or error:
            # Score by relevance
            scored = []
            for f in candidates:
                score = 0.0
                if action and action_lower in f["action"].lower():
                    score += 1.0
                if error and error_lower in f["error"].lower():
                    score += 1.0
                score += min(f["occurrence_count"] / 10, 0.5)
                scored.append((score, f))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [f for _, f in scored[:limit]]

        return sorted(candidates, key=lambda f: f["occurrence_count"], reverse=True)[:limit]

    def record_occurrence(self, failure_id: str) -> None:
        """Record that a known failure happened again."""
        for f in self._failures:
            if f["id"] == failure_id:
                f["occurrence_count"] += 1
                f["last_occurrence"] = time.time()
                break

    def update_fix(self, failure_id: str, fix: str) -> bool:
        for f in self._failures:
            if f["id"] == failure_id:
                f["fix"] = fix
                return True
        return False

    def count(self) -> int:
        return len(self._failures)

    def summarize(self) -> str:
        if not self._failures:
            return "No failures recorded"
        top = sorted(self._failures, key=lambda f: f["occurrence_count"], reverse=True)[:5]
        lines = [f"- [{f['occurrence_count']}x] {f['action']}: {f['error'][:60]}" for f in top]
        return f"Failure history ({len(self._failures)} total):\n" + "\n".join(lines)


failure_memory = FailureMemory()
