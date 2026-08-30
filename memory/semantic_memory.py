"""
Semantic Memory — Facts, entities, and persistent knowledge.
Stores what is known about the world, user, and system.
"""

import time
import uuid
from typing import Any, Optional


class SemanticMemory:
    """Stores facts, entities, and structured knowledge."""

    def __init__(self, max_entries: int = 5000):
        self.max_entries = max_entries
        self._facts: list[dict] = []

    def remember(
        self,
        content: str,
        category: str = "general",
        source: str = "",
        confidence: float = 0.9,
        metadata: Optional[dict] = None,
    ) -> str:
        """Store a new fact."""
        fact_id = f"sem-{str(uuid.uuid4())[:8]}"

        # Check for duplicate/contradictory facts
        existing = self._find_similar(content)
        if existing:
            # Update existing fact with higher confidence
            existing[0]["confidence"] = max(existing[0]["confidence"], confidence)
            existing[0]["last_verified"] = time.time()
            return existing[0]["id"]

        fact = {
            "id": fact_id,
            "content": content,
            "category": category,
            "source": source,
            "confidence": confidence,
            "metadata": metadata or {},
            "created_at": time.time(),
            "last_verified": time.time(),
            "access_count": 0,
        }
        self._facts.append(fact)

        if len(self._facts) > self.max_entries:
            self._facts.sort(key=lambda f: f["access_count"])
            self._facts = self._facts[-self.max_entries:]

        return fact_id

    def retrieve(
        self,
        query: str = "",
        category: Optional[str] = None,
        limit: int = 10,
        min_confidence: float = 0.5,
    ) -> list[dict]:
        """Retrieve relevant facts."""
        candidates = self._facts

        if category:
            candidates = [f for f in candidates if f["category"] == category]

        if min_confidence > 0:
            candidates = [f for f in candidates if f["confidence"] >= min_confidence]

        if query:
            query_lower = query.lower()
            scored = []
            for fact in candidates:
                score = 0.0
                if query_lower in fact["content"].lower():
                    score += 1.0
                if query_lower in fact["category"].lower():
                    score += 0.3
                score += fact["confidence"] * 0.2
                if score > 0:
                    scored.append((score, fact))
            scored.sort(key=lambda x: x[0], reverse=True)
            candidates = [f for _, f in scored[:limit]]
        else:
            candidates = sorted(candidates, key=lambda f: f["confidence"], reverse=True)[:limit]

        for f in candidates:
            f["access_count"] += 1

        return candidates

    def get(self, fact_id: str) -> Optional[dict]:
        for f in self._facts:
            if f["id"] == fact_id:
                f["access_count"] += 1
                return f
        return None

    def update(self, fact_id: str, **kwargs) -> bool:
        for f in self._facts:
            if f["id"] == fact_id:
                for k, v in kwargs.items():
                    if k in f:
                        f[k] = v
                f["last_verified"] = time.time()
                return True
        return False

    def _find_similar(self, content: str) -> list[dict]:
        """Find facts with similar content."""
        content_lower = content.lower()
        return [f for f in self._facts if content_lower in f["content"].lower() or f["content"].lower() in content_lower]

    def count(self) -> int:
        return len(self._facts)

    def categories(self) -> list[str]:
        return list(set(f["category"] for f in self._facts))

    def summarize(self) -> str:
        if not self._facts:
            return "No facts stored"
        cats = {}
        for f in self._facts:
            cats[f["category"]] = cats.get(f["category"], 0) + 1
        lines = [f"- {cat}: {count} facts" for cat, count in sorted(cats.items())]
        return f"Semantic memory ({len(self._facts)} facts):\n" + "\n".join(lines)


semantic_memory = SemanticMemory()
