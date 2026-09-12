"""Autonomous Memory Consolidation Pipeline for JARVIS PC.

Distills raw episodic conversation logs into long-term semantic facts,
resolves entity aliases, and synchronizes with the Knowledge Graph.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from jarvis.brain.graph import KnowledgeGraph
from jarvis.brain.memory import MemoryStore

logger = logging.getLogger(__name__)

def _clean_val(val: str) -> str:
    v = re.split(r"\b(?:and|but|while|also|with)\b|[,;.!?\n]", val, flags=re.IGNORECASE)[0]
    return v.strip()


# Triple extraction patterns: (regex, subject_default, relation, entity_type_object)
_TRIPLE_PATTERNS = [
    (re.compile(r"(?:my name is|call me)\s+([A-Za-z0-9_\-\s]{2,40})", re.IGNORECASE), "User", "has_name", "person"),
    (re.compile(r"(?:i live in|my city is|i am based in)\s+([A-Za-z0-9_\-\s]{2,40})", re.IGNORECASE), "User", "located_in", "location"),
    (re.compile(r"(?:i (?:code with|use|work in)|my (?:ide|editor) is)\s+([A-Za-z0-9_\-\s]{2,30})", re.IGNORECASE), "User", "uses_tool", "tool"),
    (re.compile(r"(?:i am working on|my project is|work on project)\s+([A-Za-z0-9_\-\s]{2,40})", re.IGNORECASE), "User", "works_on_project", "project"),
    (re.compile(r"(?:my favorite|i prefer)\s+([A-Za-z0-9_\-\s]+)\s+(?:is|over)\s+([A-Za-z0-9_\-\s]+)", re.IGNORECASE), "User", "prefers", "preference"),
    (re.compile(r"([A-Za-z0-9_\-]+)\s+is\s+a\s+([A-Za-z0-9_\-\s]+)", re.IGNORECASE), None, "is_a", "concept"),
    (re.compile(r"([A-Za-z0-9_\-]+)\s+depends\s+on\s+([A-Za-z0-9_\-]+)", re.IGNORECASE), None, "depends_on", "dependency"),
]


class MemoryConsolidator:
    """Consolidates episodic dialogue history into structured relational facts."""

    def __init__(
        self,
        memory_store: Optional[MemoryStore] = None,
        graph: Optional[KnowledgeGraph] = None,
    ) -> None:
        if memory_store is None:
            from jarvis.system.paths import get_app_paths
            memory_store = MemoryStore(get_app_paths().state / "memory.db")
        self.memory = memory_store
        self.graph = graph or KnowledgeGraph()

    def extract_triples_from_text(self, text: str) -> List[Tuple[str, str, str, str]]:
        """Extract (subject, relation, target, target_type) triples from text."""
        triples: List[Tuple[str, str, str, str]] = []
        clean = text.strip()

        for pattern, default_subj, rel, obj_type in _TRIPLE_PATTERNS:
            for match in pattern.finditer(clean):
                groups = match.groups()
                if default_subj and len(groups) == 1:
                    obj = _clean_val(groups[0])
                    if obj:
                        triples.append((default_subj, rel, obj, obj_type))
                elif default_subj and len(groups) == 2:
                    # E.g. favorite X is Y
                    prop = _clean_val(groups[0])
                    val = _clean_val(groups[1])
                    if prop and val:
                        triples.append((default_subj, f"favorite_{prop}", val, obj_type))
                elif default_subj is None and len(groups) >= 2:
                    subj = _clean_val(groups[0])
                    obj = _clean_val(groups[1])
                    if subj and obj:
                        triples.append((subj, rel, obj, obj_type))

        return triples

    def consolidate(self, limit: int = 50) -> Dict[str, Any]:
        """Perform batch consolidation of recent conversation turns into the Knowledge Graph."""
        episodes = self.memory.recent(limit=limit)
        if not episodes:
            return {"consolidated_episodes": 0, "new_relations": 0, "extracted_facts": 0, "total_entities": self.graph.stats()["total_entities"], "total_relations": self.graph.stats()["total_relations"]}

        new_relations = 0
        extracted_facts = 0

        # Ensure root 'User' and 'JARVIS' entities exist
        user_entity = self.graph.find_or_create_entity("User", entity_type="person")
        jarvis_entity = self.graph.find_or_create_entity("JARVIS", entity_type="assistant")
        self.graph.add_relation(jarvis_entity, "assists", user_entity, confidence=1.0)

        for ep in episodes:
            user_msg = ep.get("user", "")
            if not user_msg:
                continue

            triples = self.extract_triples_from_text(user_msg)
            for subj, rel, obj, obj_type in triples:
                # 1. Update Knowledge Graph
                s_ent = self.graph.find_or_create_entity(subj, entity_type="person" if subj == "User" else "concept")
                t_ent = self.graph.find_or_create_entity(obj, entity_type=obj_type)
                self.graph.add_relation(
                    source=s_ent,
                    relation_type=rel,
                    target=t_ent,
                    confidence=0.95,
                    evidence=user_msg[:120],
                )
                new_relations += 1

                # 2. Update semantic facts in memory store
                if subj == "User":
                    self.memory.store_fact(
                        key=rel,
                        value=obj,
                        category=obj_type,
                        subject="user",
                        predicate=rel,
                        confidence=0.95,
                        source="consolidator",
                    )
                    self.memory.update_profile_entry(key=rel, value=obj, category=obj_type)
                    extracted_facts += 1

        stats = self.graph.stats()
        logger.info(
            "Memory consolidation complete: %d episodes scanned, %d relations committed. Total graph nodes: %d",
            len(episodes),
            new_relations,
            stats["total_entities"],
        )

        return {
            "consolidated_episodes": len(episodes),
            "new_relations": new_relations,
            "extracted_facts": extracted_facts,
            "total_entities": stats["total_entities"],
            "total_relations": stats["total_relations"],
        }
