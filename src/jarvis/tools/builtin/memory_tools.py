"""Builtin agent tools for Long-Term Semantic Memory & User Profile Knowledge Graph."""

from __future__ import annotations

import logging
from typing import Optional

from jarvis.brain.memory import MemoryStore
from jarvis.system.paths import get_app_paths

logger = logging.getLogger(__name__)


def _get_memory_store() -> MemoryStore:
    """Resolve default application SQLite MemoryStore."""
    db_path = get_app_paths().state / "memory.db"
    return MemoryStore(db_path)


def remember_fact(key: str, value: str, category: str = "general") -> str:
    """Explicitly store a user preference, personal detail, or semantic fact into persistent memory."""
    store = _get_memory_store()
    clean_key = key.strip()
    clean_val = value.strip()
    clean_cat = category.strip().lower()

    fact_id = store.store_fact(
        key=clean_key,
        value=clean_val,
        category=clean_cat,
        subject="user",
        predicate="preference",
        confidence=1.0,
        source="agent_tool",
    )
    return f"Memorized [{clean_cat}] '{clean_key}': '{clean_val}' (Record ID: {fact_id})."


def recall_facts(query: str, category: Optional[str] = None) -> str:
    """Search and recall relevant semantic facts, preferences, and long-term memories using BM25 ranking."""
    store = _get_memory_store()
    facts = store.recall_facts(query=query, category=category, limit=6)

    if not facts:
        return f"No matching memories found for query '{query}'."

    lines = [f"Recalled {len(facts)} memory record(s) matching '{query}':"]
    for f in facts:
        lines.append(f"• [{f['category'].upper()}] {f['key']}: {f['value']} (confidence: {f['confidence']:.2f})")

    return "\n".join(lines)


def forget_fact(key_or_id: str) -> str:
    """Remove an outdated or requested fact/preference from persistent memory."""
    store = _get_memory_store()
    target = key_or_id.strip()
    ok = store.delete_fact(target)

    if ok:
        return f"Successfully removed fact '{target}' from memory."
    return f"Fact '{target}' was not found in memory."


def get_user_profile() -> str:
    """Retrieve a structured overview of the operator's saved profile, preferences, and personal facts."""
    store = _get_memory_store()
    profile = store.get_user_profile()

    if not profile:
        return "No user profile attributes or preferences recorded in memory yet."

    lines = ["JARVIS Operator Profile & Stored Preferences:"]
    lines.append("=" * 60)
    for category, entries in profile.items():
        lines.append(f"\n[{category.upper()}]")
        for k, v in entries.items():
            lines.append(f"• {k:<20}: {v}")
    lines.append("\n" + "=" * 60)

    return "\n".join(lines)
