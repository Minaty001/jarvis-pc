"""SQLite-backed relational Knowledge Graph store for JARVIS PC.

Supports entity extraction, multi-hop relation traversal, subgraph queries,
and entity resolution.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class GraphEntity:
    id: int
    name: str
    entity_type: str = "concept"
    aliases: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: int = 0
    updated_at: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "entity_type": self.entity_type,
            "aliases": self.aliases,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class GraphRelation:
    id: int
    source_id: int
    source_name: str
    target_id: int
    target_name: str
    relation_type: str
    weight: float = 1.0
    confidence: float = 1.0
    evidence: str = ""
    created_at: int = 0
    updated_at: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "source_name": self.source_name,
            "target_id": self.target_id,
            "target_name": self.target_name,
            "relation_type": self.relation_type,
            "weight": self.weight,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def _init_graph_db(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")

    conn.execute(
        "CREATE TABLE IF NOT EXISTS graph_entities ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "name TEXT UNIQUE NOT NULL, "
        "entity_type TEXT NOT NULL, "
        "aliases_json TEXT NOT NULL DEFAULT '[]', "
        "metadata_json TEXT NOT NULL DEFAULT '{}', "
        "created_at INTEGER NOT NULL, "
        "updated_at INTEGER NOT NULL)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_entities_type ON graph_entities(entity_type)")

    conn.execute(
        "CREATE TABLE IF NOT EXISTS graph_relations ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "source_id INTEGER NOT NULL REFERENCES graph_entities(id) ON DELETE CASCADE, "
        "target_id INTEGER NOT NULL REFERENCES graph_entities(id) ON DELETE CASCADE, "
        "relation_type TEXT NOT NULL, "
        "weight REAL NOT NULL DEFAULT 1.0, "
        "confidence REAL NOT NULL DEFAULT 1.0, "
        "evidence TEXT NOT NULL DEFAULT '', "
        "created_at INTEGER NOT NULL, "
        "updated_at INTEGER NOT NULL, "
        "UNIQUE(source_id, target_id, relation_type))"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rel_source ON graph_relations(source_id, relation_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rel_target ON graph_relations(target_id, relation_type)")
    conn.commit()


class KnowledgeGraph:
    """Manages nodes, directional relationships, and graph traversal queries."""

    def __init__(self, path: str | Path | None = None) -> None:
        if path is None:
            from jarvis.system.paths import get_app_paths
            path = get_app_paths().data / "knowledge_graph.db"
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False, timeout=30.0)
        _init_graph_db(self._conn)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ── Entity Management ───────────────────────────────────────────────
    def add_entity(
        self,
        name: str,
        entity_type: str = "concept",
        aliases: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> GraphEntity:
        """Create or update an entity in the graph."""
        clean_name = name.strip()
        now = int(time.time())
        aliases_json = json.dumps(aliases or [])
        metadata_json = json.dumps(metadata or {})

        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "INSERT INTO graph_entities (name, entity_type, aliases_json, metadata_json, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(name) DO UPDATE SET "
                "entity_type=excluded.entity_type, "
                "aliases_json=excluded.aliases_json, "
                "metadata_json=excluded.metadata_json, "
                "updated_at=excluded.updated_at RETURNING id",
                (clean_name, entity_type, aliases_json, metadata_json, now, now),
            )
            row = cur.fetchone()
            entity_id = row[0]
            self._conn.commit()

        return GraphEntity(
            id=entity_id,
            name=clean_name,
            entity_type=entity_type,
            aliases=aliases or [],
            metadata=metadata or {},
            created_at=now,
            updated_at=now,
        )

    def get_entity(self, name_or_id: str | int) -> Optional[GraphEntity]:
        """Fetch entity by exact name or integer ID."""
        with self._lock:
            cur = self._conn.cursor()
            if isinstance(name_or_id, int) or (isinstance(name_or_id, str) and name_or_id.isdigit()):
                cur.execute(
                    "SELECT id, name, entity_type, aliases_json, metadata_json, created_at, updated_at "
                    "FROM graph_entities WHERE id = ?",
                    (int(name_or_id),),
                )
            else:
                clean_name = str(name_or_id).strip()
                cur.execute(
                    "SELECT id, name, entity_type, aliases_json, metadata_json, created_at, updated_at "
                    "FROM graph_entities WHERE LOWER(name) = LOWER(?)",
                    (clean_name,),
                )
            row = cur.fetchone()
            if not row:
                return None
            return GraphEntity(
                id=row[0],
                name=row[1],
                entity_type=row[2],
                aliases=json.loads(row[3]),
                metadata=json.loads(row[4]),
                created_at=row[5],
                updated_at=row[6],
            )

    def find_or_create_entity(
        self,
        name: str,
        entity_type: str = "concept",
        aliases: Optional[List[str]] = None,
    ) -> GraphEntity:
        existing = self.get_entity(name)
        if existing:
            return existing
        return self.add_entity(name, entity_type=entity_type, aliases=aliases)

    def list_entities(self, entity_type: Optional[str] = None, limit: int = 100) -> List[GraphEntity]:
        with self._lock:
            cur = self._conn.cursor()
            if entity_type:
                cur.execute(
                    "SELECT id, name, entity_type, aliases_json, metadata_json, created_at, updated_at "
                    "FROM graph_entities WHERE entity_type = ? ORDER BY updated_at DESC LIMIT ?",
                    (entity_type, limit),
                )
            else:
                cur.execute(
                    "SELECT id, name, entity_type, aliases_json, metadata_json, created_at, updated_at "
                    "FROM graph_entities ORDER BY updated_at DESC LIMIT ?",
                    (limit,),
                )
            return [
                GraphEntity(
                    id=r[0],
                    name=r[1],
                    entity_type=r[2],
                    aliases=json.loads(r[3]),
                    metadata=json.loads(r[4]),
                    created_at=r[5],
                    updated_at=r[6],
                )
                for r in cur.fetchall()
            ]

    # ── Relation Management ─────────────────────────────────────────────
    def add_relation(
        self,
        source: str | GraphEntity,
        relation_type: str,
        target: str | GraphEntity,
        weight: float = 1.0,
        confidence: float = 1.0,
        evidence: str = "",
    ) -> GraphRelation:
        """Create or update a directed relationship edge between two entities."""
        source_ent = source if isinstance(source, GraphEntity) else self.find_or_create_entity(str(source))
        target_ent = target if isinstance(target, GraphEntity) else self.find_or_create_entity(str(target))
        clean_rel = relation_type.strip().lower().replace(" ", "_")
        now = int(time.time())

        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "INSERT INTO graph_relations (source_id, target_id, relation_type, weight, confidence, evidence, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(source_id, target_id, relation_type) DO UPDATE SET "
                "weight=excluded.weight, "
                "confidence=excluded.confidence, "
                "evidence=excluded.evidence, "
                "updated_at=excluded.updated_at RETURNING id",
                (source_ent.id, target_ent.id, clean_rel, float(weight), float(confidence), evidence, now, now),
            )
            rel_id = cur.fetchone()[0]
            self._conn.commit()

        return GraphRelation(
            id=rel_id,
            source_id=source_ent.id,
            source_name=source_ent.name,
            target_id=target_ent.id,
            target_name=target_ent.name,
            relation_type=clean_rel,
            weight=weight,
            confidence=confidence,
            evidence=evidence,
            created_at=now,
            updated_at=now,
        )

    def get_relations_for_entity(self, name_or_id: str | int) -> List[GraphRelation]:
        """Fetch all outgoing and incoming relations for an entity."""
        ent = self.get_entity(name_or_id)
        if not ent:
            return []

        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT r.id, r.source_id, s.name, r.target_id, t.name, r.relation_type, r.weight, r.confidence, r.evidence, r.created_at, r.updated_at "
                "FROM graph_relations r "
                "JOIN graph_entities s ON r.source_id = s.id "
                "JOIN graph_entities t ON r.target_id = t.id "
                "WHERE r.source_id = ? OR r.target_id = ? "
                "ORDER BY r.weight DESC, r.confidence DESC",
                (ent.id, ent.id),
            )
            return [
                GraphRelation(
                    id=r[0],
                    source_id=r[1],
                    source_name=r[2],
                    target_id=r[3],
                    target_name=r[4],
                    relation_type=r[5],
                    weight=r[6],
                    confidence=r[7],
                    evidence=r[8],
                    created_at=r[9],
                    updated_at=r[10],
                )
                for r in cur.fetchall()
            ]

    # ── Graph Traversal & Subgraphs ─────────────────────────────────────
    def get_subgraph(
        self,
        start_entity: str,
        depth: int = 2,
        max_nodes: int = 30,
    ) -> Dict[str, Any]:
        """Extract multi-hop neighborhood graph around start_entity."""
        root = self.get_entity(start_entity)
        if not root:
            return {"entities": [], "relations": []}

        visited_ids: Set[int] = {root.id}
        entities_dict: Dict[int, GraphEntity] = {root.id: root}
        relations_list: List[GraphRelation] = []
        current_frontier: Set[int] = {root.id}

        for _ in range(depth):
            if not current_frontier or len(visited_ids) >= max_nodes:
                break
            next_frontier: Set[int] = set()

            for node_id in current_frontier:
                rels = self.get_relations_for_entity(node_id)
                for rel in rels:
                    if rel not in relations_list:
                        relations_list.append(rel)

                    other_id = rel.target_id if rel.source_id == node_id else rel.source_id
                    if other_id not in visited_ids and len(visited_ids) < max_nodes:
                        visited_ids.add(other_id)
                        next_frontier.add(other_id)
                        ent = self.get_entity(other_id)
                        if ent:
                            entities_dict[other_id] = ent

            current_frontier = next_frontier

        return {
            "root": root.name,
            "entities": [e.to_dict() for e in entities_dict.values()],
            "relations": [r.to_dict() for r in relations_list],
        }

    def format_subgraph_context(self, start_entity: str, depth: int = 2) -> str:
        """Format neighborhood subgraph into clean bulleted facts for system prompt injection."""
        subgraph = self.get_subgraph(start_entity, depth=depth)
        if not subgraph.get("relations"):
            return ""

        lines = [f"Relational Knowledge for '{start_entity}':"]
        for r in subgraph["relations"]:
            src = r["source_name"]
            rel = r["relation_type"].replace("_", " ")
            tgt = r["target_name"]
            conf = int(r["confidence"] * 100)
            lines.append(f"• ({src}) --[{rel}]--> ({tgt}) [{conf}% confidence]")
        return "\n".join(lines)

    def stats(self) -> Dict[str, int]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT COUNT(*) FROM graph_entities")
            total_entities = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM graph_relations")
            total_relations = cur.fetchone()[0]
            return {
                "total_entities": total_entities,
                "total_relations": total_relations,
            }
