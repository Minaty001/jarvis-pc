"""
Episodic Memory — Past task experiences and conversation episodes.
Stores what happened, when, and outcomes.
"""

import time
import uuid
from typing import Any, Optional


class EpisodicMemory:
    """Stores past experiences with timestamps, outcomes, and context."""

    def __init__(self, max_entries: int = 1000):
        self.max_entries = max_entries
        self._episodes: list[dict] = []

    def remember(
        self,
        content: str,
        outcome: str = "unknown",
        context: Optional[dict] = None,
        tags: Optional[list[str]] = None,
        importance: float = 0.5,
    ) -> str:
        """Store a new episode. Returns episode ID."""
        episode_id = f"ep-{str(uuid.uuid4())[:8]}"
        episode = {
            "id": episode_id,
            "content": content,
            "outcome": outcome,
            "context": context or {},
            "tags": tags or [],
            "importance": importance,
            "created_at": time.time(),
            "access_count": 0,
        }
        self._episodes.append(episode)

        # Evict oldest low-importance episodes if over limit
        if len(self._episodes) > self.max_entries:
            self._episodes.sort(key=lambda e: (e["importance"], e["created_at"]))
            self._episodes = self._episodes[-self.max_entries:]

        return episode_id

    def retrieve(
        self,
        query: str = "",
        tags: Optional[list[str]] = None,
        limit: int = 10,
        min_importance: float = 0.0,
    ) -> list[dict]:
        """Retrieve relevant episodes."""
        candidates = self._episodes

        # Filter by importance
        if min_importance > 0:
            candidates = [e for e in candidates if e["importance"] >= min_importance]

        # Filter by tags
        if tags:
            candidates = [e for e in candidates if any(t in e["tags"] for t in tags)]

        # Score by relevance to query
        if query:
            query_lower = query.lower()
            scored = []
            for ep in candidates:
                score = 0.0
                if query_lower in ep["content"].lower():
                    score += 1.0
                for tag in ep["tags"]:
                    if query_lower in tag.lower():
                        score += 0.5
                if score > 0:
                    scored.append((score, ep))
            scored.sort(key=lambda x: x[0], reverse=True)
            candidates = [ep for _, ep in scored[:limit]]
        else:
            # Return most recent
            candidates = sorted(candidates, key=lambda e: e["created_at"], reverse=True)[:limit]

        # Update access counts
        for ep in candidates:
            ep["access_count"] += 1

        return candidates

    def get(self, episode_id: str) -> Optional[dict]:
        for ep in self._episodes:
            if ep["id"] == episode_id:
                ep["access_count"] += 1
                return ep
        return None

    def update_outcome(self, episode_id: str, outcome: str) -> bool:
        for ep in self._episodes:
            if ep["id"] == episode_id:
                ep["outcome"] = outcome
                return True
        return False

    def count(self) -> int:
        return len(self._episodes)

    def summarize(self) -> str:
        if not self._episodes:
            return "No episodes recorded"
        recent = sorted(self._episodes, key=lambda e: e["created_at"], reverse=True)[:5]
        lines = [f"- [{e['outcome']}] {e['content'][:80]}" for e in recent]
        return f"Recent episodes ({len(self._episodes)} total):\n" + "\n".join(lines)


episodic_memory = EpisodicMemory()
