"""
Procedural Memory — How-to knowledge and successful strategies.
Stores proven approaches for common tasks.
"""

import time
import uuid
from typing import Any, Optional


class ProceduralMemory:
    """Stores procedures, strategies, and how-to knowledge."""

    def __init__(self, max_entries: int = 500):
        self.max_entries = max_entries
        self._procedures: list[dict] = []

    def remember(
        self,
        name: str,
        steps: list[str],
        context: str = "",
        success_count: int = 1,
        failure_count: int = 0,
        metadata: Optional[dict] = None,
    ) -> str:
        """Store a new procedure."""
        # Check if procedure already exists
        existing = [p for p in self._procedures if p["name"].lower() == name.lower()]
        if existing:
            existing[0]["success_count"] += success_count
            existing[0]["last_used"] = time.time()
            existing[0]["steps"] = steps
            return existing[0]["id"]

        proc_id = f"proc-{str(uuid.uuid4())[:8]}"
        procedure = {
            "id": proc_id,
            "name": name,
            "steps": steps,
            "context": context,
            "success_count": success_count,
            "failure_count": failure_count,
            "success_rate": success_count / max(1, success_count + failure_count),
            "metadata": metadata or {},
            "created_at": time.time(),
            "last_used": time.time(),
        }
        self._procedures.append(procedure)

        if len(self._procedures) > self.max_entries:
            self._procedures.sort(key=lambda p: p["success_rate"])
            self._procedures = self._procedures[-self.max_entries:]

        return proc_id

    def retrieve(
        self,
        query: str = "",
        min_success_rate: float = 0.5,
        limit: int = 5,
    ) -> list[dict]:
        """Retrieve relevant procedures."""
        candidates = [p for p in self._procedures if p["success_rate"] >= min_success_rate]

        if query:
            query_lower = query.lower()
            scored = []
            for proc in candidates:
                score = 0.0
                if query_lower in proc["name"].lower():
                    score += 1.0
                if query_lower in proc["context"].lower():
                    score += 0.5
                score += proc["success_rate"] * 0.3
                if score > 0:
                    scored.append((score, proc))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [p for _, p in scored[:limit]]

        return sorted(candidates, key=lambda p: p["success_rate"], reverse=True)[:limit]

    def record_outcome(self, proc_id: str, success: bool) -> None:
        """Record the outcome of using a procedure."""
        for p in self._procedures:
            if p["id"] == proc_id:
                if success:
                    p["success_count"] += 1
                else:
                    p["failure_count"] += 1
                p["success_rate"] = p["success_count"] / max(1, p["success_count"] + p["failure_count"])
                p["last_used"] = time.time()
                break

    def count(self) -> int:
        return len(self._procedures)

    def summarize(self) -> str:
        if not self._procedures:
            return "No procedures stored"
        top = sorted(self._procedures, key=lambda p: p["success_rate"], reverse=True)[:5]
        lines = [f"- {p['name']} ({p['success_rate']:.0%} success, {len(p['steps'])} steps)" for p in top]
        return f"Procedures ({len(self._procedures)} total):\n" + "\n".join(lines)


procedural_memory = ProceduralMemory()
