"""
Preference Memory — User-approved preferences and settings.
Explicitly learned from user feedback.
"""

import time
import uuid
from typing import Any, Optional


class PreferenceMemory:
    """Stores user preferences with explicit approval tracking."""

    def __init__(self, max_entries: int = 200):
        self.max_entries = max_entries
        self._preferences: list[dict] = []

    def remember(
        self,
        key: str,
        value: Any,
        category: str = "general",
        approved: bool = True,
        source: str = "user",
    ) -> str:
        """Store a user preference."""
        # Update existing preference
        for pref in self._preferences:
            if pref["key"].lower() == key.lower():
                pref["value"] = value
                pref["updated_at"] = time.time()
                pref["approved"] = approved
                return pref["id"]

        pref_id = f"pref-{str(uuid.uuid4())[:8]}"
        preference = {
            "id": pref_id,
            "key": key,
            "value": value,
            "category": category,
            "approved": approved,
            "source": source,
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        self._preferences.append(preference)

        if len(self._preferences) > self.max_entries:
            self._preferences = self._preferences[-self.max_entries:]

        return pref_id

    def get(self, key: str, default: Any = None) -> Any:
        """Get a preference value by key."""
        for pref in self._preferences:
            if pref["key"].lower() == key.lower():
                return pref["value"]
        return default

    def retrieve(
        self,
        category: Optional[str] = None,
        query: str = "",
        limit: int = 20,
    ) -> list[dict]:
        """Retrieve preferences."""
        candidates = self._preferences

        if category:
            candidates = [p for p in candidates if p["category"] == category]

        if query:
            query_lower = query.lower()
            candidates = [p for p in candidates if query_lower in p["key"].lower() or query_lower in str(p["value"]).lower()]

        return candidates[:limit]

    def delete(self, key: str) -> bool:
        for i, pref in enumerate(self._preferences):
            if pref["key"].lower() == key.lower():
                self._preferences.pop(i)
                return True
        return False

    def count(self) -> int:
        return len(self._preferences)

    def to_dict(self) -> dict:
        return {p["key"]: p["value"] for p in self._preferences if p["approved"]}

    def summarize(self) -> str:
        if not self._preferences:
            return "No preferences stored"
        lines = [f"- {p['key']}: {str(p['value'])[:50]}" for p in self._preferences[:10]]
        return f"Preferences ({len(self._preferences)} total):\n" + "\n".join(lines)


preference_memory = PreferenceMemory()
