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


def query_knowledge_graph(entity_name: str, depth: int = 2) -> str:
    """Traverse and retrieve relational facts and connected entities from the Knowledge Graph."""
    from jarvis.brain.graph import KnowledgeGraph
    graph = KnowledgeGraph()
    res = graph.format_subgraph_context(start_entity=entity_name, depth=depth)
    if not res:
        return f"No relational graph connections found for entity '{entity_name}'."
    return res


def consolidate_user_memory(limit: int = 50) -> str:
    """Distill recent conversation history into structured facts and entities in the Knowledge Graph."""
    from jarvis.brain.consolidator import MemoryConsolidator
    consolidator = MemoryConsolidator(memory_store=_get_memory_store())
    metrics = consolidator.consolidate(limit=limit)
    return (
        f"Memory consolidation completed:\n"
        f"• Episodes processed: {metrics['consolidated_episodes']}\n"
        f"• New relations added: {metrics['new_relations']}\n"
        f"• Facts extracted:     {metrics['extracted_facts']}\n"
        f"• Total graph nodes:   {metrics['total_entities']}\n"
        f"• Total graph edges:   {metrics['total_relations']}"
    )


def add_graph_fact(source_entity: str, relation: str, target_entity: str, confidence: float = 0.95) -> str:
    """Add a verified relationship edge between two entities in the Knowledge Graph."""
    from jarvis.brain.graph import KnowledgeGraph
    graph = KnowledgeGraph()
    rel = graph.add_relation(
        source=source_entity.strip(),
        relation_type=relation.strip(),
        target=target_entity.strip(),
        confidence=confidence,
        evidence="Manual agent entry",
    )
    return f"Graph relationship added: ({rel.source_name}) --[{rel.relation_type}]--> ({rel.target_name}) [confidence: {int(rel.confidence * 100)}%]."


def list_known_entities(entity_type: Optional[str] = None) -> str:
    """List all entities tracked in the Knowledge Graph, optionally filtered by type."""
    from jarvis.brain.graph import KnowledgeGraph
    graph = KnowledgeGraph()
    entities = graph.list_entities(entity_type=entity_type, limit=50)
    if not entities:
        return "No entities recorded in the Knowledge Graph."

    lines = [f"Tracked Knowledge Graph Entities ({len(entities)}):"]
    for e in entities:
        lines.append(f"• {e.name:<25} [type: {e.entity_type}]")
    return "\n".join(lines)
