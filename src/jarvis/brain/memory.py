"""Long-term memory backed by SQLite FTS5 full-text search.

Stores episodic turns (user + assistant reply) and metacognitive reflections
(lessons learned and procedural recipes) in SQLite with FTS5 indexes and recalls
the most relevant entries via BM25 ranking.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

MAX_EPISODES = 500
MAX_REFLECTIONS = 200
MAX_FACTS = 1000


def _open(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    # Episodic conversation turns
    conn.execute(
        "CREATE TABLE IF NOT EXISTS episodes ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, user TEXT, reply TEXT)"
    )
    conn.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS episodes_fts USING fts5(user, reply, content='episodes', content_rowid='id')"
    )

    # Metacognitive reflections and learned procedural patterns
    conn.execute(
        "CREATE TABLE IF NOT EXISTS reflections ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, goal_query TEXT, "
        "category TEXT, lesson TEXT, recipe_json TEXT, verified INTEGER, "
        "success_count INTEGER, failure_count INTEGER)"
    )
    conn.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS reflections_fts USING fts5("
        "goal_query, lesson, content='reflections', content_rowid='id')"
    )

    # Long-term semantic facts and entity relational knowledge graph
    conn.execute(
        "CREATE TABLE IF NOT EXISTS facts ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, subject TEXT, "
        "predicate TEXT, key TEXT, value TEXT, category TEXT, confidence REAL, "
        "source TEXT)"
    )
    conn.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5("
        "subject, predicate, key, value, category, content='facts', content_rowid='id')"
    )

    # Key-value user profile summary table
    conn.execute(
        "CREATE TABLE IF NOT EXISTS user_profile ("
        "key TEXT PRIMARY KEY, value TEXT, category TEXT, updated_at INTEGER)"
    )
    conn.commit()
    return conn


class MemoryStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._migrate_if_needed()
        self._conn = _open(self.path)

    def _migrate_if_needed(self) -> None:
        """One-time migration of a pre-SQLite JSONL memory file."""
        if not self.path.exists() or self.path.read_bytes().startswith(b"SQLite format 3"):
            return
        records: list[tuple] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                records.append((record.get("ts") or int(time.time()), record.get("user", ""), record.get("reply", "")))
        self.path.unlink()  # remove JSONL so _open can create fresh sqlite DB
        conn = _open(self.path)
        conn.executemany("INSERT INTO episodes (ts, user, reply) VALUES (?, ?, ?)", records)
        conn.execute("INSERT INTO episodes_fts(episodes_fts) VALUES('rebuild')")
        conn.commit()
        conn.close()

    # ── Episodic Conversation Memory ────────────────────────────────────
    def add(self, user: str, reply: str) -> None:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO episodes (ts, user, reply) VALUES (?, ?, ?)",
                (int(time.time()), user, reply),
            )
            self._conn.execute(
                "INSERT INTO episodes_fts (rowid, user, reply) VALUES (?, ?, ?)",
                (cur.lastrowid, user, reply),
            )
            self._conn.commit()
            self._trim()

    def recall(self, query: str, limit: int = 4) -> list[str]:
        terms = [t for t in query.split() if t]
        if not terms:
            return []
        escaped_terms = [t.replace('"', '""') for t in terms]
        match = " OR ".join(f'"{t}"' for t in escaped_terms)
        with self._lock:
            try:
                rows = self._conn.execute(
                    "SELECT user, reply FROM episodes_fts "
                    "WHERE episodes_fts MATCH ? ORDER BY bm25(episodes_fts) LIMIT ?",
                    (match, limit),
                ).fetchall()
                return [f"user: {user} | jarvis: {reply}" for user, reply in rows]
            except sqlite3.OperationalError:
                return []

    def recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return most recent conversation turns for UI display."""
        with self._lock:
            try:
                rows = self._conn.execute(
                    "SELECT ts, user, reply FROM episodes ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
                return [
                    {
                        "ts": r[0],
                        "category": "chat",
                        "content": f"User: {r[1]} -> Jarvis: {r[2]}",
                    }
                    for r in rows
                ]
            except sqlite3.OperationalError:
                return []

    # ── Metacognitive Reflection & Procedural Memory ────────────────────
    def store_reflection(
        self,
        goal_query: str,
        lesson: str,
        category: str = "general",
        recipe: Optional[Any] = None,
        verified: bool = True,
    ) -> int:
        """Store or update a learned reflection lesson in SQLite FTS5."""
        clean_goal = goal_query.strip()
        clean_lesson = lesson.strip()
        recipe_json = json.dumps(recipe) if recipe is not None else ""
        now = int(time.time())

        with self._lock:
            # Check for existing duplicate lesson to avoid bloat
            row = self._conn.execute(
                "SELECT id, success_count, failure_count FROM reflections "
                "WHERE goal_query = ? AND lesson = ?",
                (clean_goal, clean_lesson),
            ).fetchone()

            if row:
                ref_id, succ, fail = row
                if verified:
                    succ += 1
                else:
                    fail += 1
                self._conn.execute(
                    "UPDATE reflections SET ts = ?, success_count = ?, failure_count = ?, recipe_json = ? WHERE id = ?",
                    (now, succ, fail, recipe_json, ref_id),
                )
                self._conn.commit()
                return ref_id

            # Insert new reflection
            succ = 1 if verified else 0
            fail = 0 if verified else 1
            cur = self._conn.execute(
                "INSERT INTO reflections (ts, goal_query, category, lesson, recipe_json, verified, success_count, failure_count) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (now, clean_goal, category, clean_lesson, recipe_json, 1 if verified else 0, succ, fail),
            )
            ref_id = cur.lastrowid
            self._conn.execute(
                "INSERT INTO reflections_fts (rowid, goal_query, lesson) VALUES (?, ?, ?)",
                (ref_id, clean_goal, clean_lesson),
            )
            self._conn.commit()
            self._trim_reflections()
            return ref_id

    def recall_reflections(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Recall relevant lessons and procedural patterns using BM25 ranking."""
        terms = [t for t in query.split() if t]
        if not terms:
            return []
        escaped_terms = [t.replace('"', '""') for t in terms]
        match = " OR ".join(f'"{t}"' for t in escaped_terms)
        with self._lock:
            try:
                rows = self._conn.execute(
                    "SELECT r.id, r.goal_query, r.category, r.lesson, r.recipe_json, r.verified, "
                    "r.success_count, r.failure_count FROM reflections r "
                    "JOIN reflections_fts fts ON r.id = fts.rowid "
                    "WHERE reflections_fts MATCH ? "
                    "ORDER BY bm25(reflections_fts) ASC, r.success_count DESC LIMIT ?",
                    (match, limit),
                ).fetchall()
                results = []
                for r in rows:
                    recipe = json.loads(r[4]) if r[4] else None
                    results.append({
                        "id": r[0],
                        "goal_query": r[1],
                        "category": r[2],
                        "lesson": r[3],
                        "recipe": recipe,
                        "verified": bool(r[5]),
                        "success_count": r[6],
                        "failure_count": r[7],
                    })
                return results
            except sqlite3.OperationalError:
                return []

    def list_reflections(self, limit: int = 20) -> List[Dict[str, Any]]:
        """List most recent reflections and patterns."""
        with self._lock:
            try:
                rows = self._conn.execute(
                    "SELECT id, ts, goal_query, category, lesson, recipe_json, verified, "
                    "success_count, failure_count FROM reflections ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
                results = []
                for r in rows:
                    recipe = json.loads(r[5]) if r[5] else None
                    results.append({
                        "id": r[0],
                        "ts": r[1],
                        "goal_query": r[2],
                        "category": r[3],
                        "lesson": r[4],
                        "recipe": recipe,
                        "verified": bool(r[6]),
                        "success_count": r[7],
                        "failure_count": r[8],
                    })
                return results
            except sqlite3.OperationalError:
                return []

    # ── Long-term Semantic Facts & User Profile Knowledge Graph ─────────
    def store_fact(
        self,
        key: str,
        value: str,
        category: str = "general",
        subject: str = "user",
        predicate: str = "preference",
        confidence: float = 1.0,
        source: str = "conversation",
    ) -> int:
        """Store or update a long-term semantic fact / preference in SQLite FTS5."""
        clean_key = key.strip()
        clean_val = value.strip()
        clean_cat = category.strip().lower()
        clean_subj = subject.strip().lower()
        clean_pred = predicate.strip().lower()
        now = int(time.time())

        with self._lock:
            # Check for existing fact with matching subject and key
            row = self._conn.execute(
                "SELECT id FROM facts WHERE subject = ? AND key = ?",
                (clean_subj, clean_key),
            ).fetchone()

            if row:
                fact_id = row[0]
                self._conn.execute(
                    "UPDATE facts SET ts = ?, predicate = ?, value = ?, category = ?, confidence = ?, source = ? WHERE id = ?",
                    (now, clean_pred, clean_val, clean_cat, confidence, source, fact_id),
                )
                self._conn.execute(
                    "UPDATE facts_fts SET subject = ?, predicate = ?, key = ?, value = ?, category = ? WHERE rowid = ?",
                    (clean_subj, clean_pred, clean_key, clean_val, clean_cat, fact_id),
                )
            else:
                cur = self._conn.execute(
                    "INSERT INTO facts (ts, subject, predicate, key, value, category, confidence, source) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (now, clean_subj, clean_pred, clean_key, clean_val, clean_cat, confidence, source),
                )
                fact_id = cur.lastrowid
                self._conn.execute(
                    "INSERT INTO facts_fts (rowid, subject, predicate, key, value, category) VALUES (?, ?, ?, ?, ?, ?)",
                    (fact_id, clean_subj, clean_pred, clean_key, clean_val, clean_cat),
                )

            # If this is a user property/preference, keep user_profile table in sync
            if clean_subj == "user":
                self._conn.execute(
                    "INSERT INTO user_profile (key, value, category, updated_at) VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value, category = excluded.category, updated_at = excluded.updated_at",
                    (clean_key, clean_val, clean_cat, now),
                )

            self._conn.commit()
            self._trim_facts()
            return fact_id

    def recall_facts(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Recall relevant semantic facts using FTS5 BM25 ranking."""
        terms = [t for t in query.split() if t]
        if not terms:
            return []
        escaped_terms = [t.replace('"', '""') for t in terms]
        match = " OR ".join(f'"{t}"' for t in escaped_terms)
        with self._lock:
            try:
                if category:
                    rows = self._conn.execute(
                        "SELECT f.id, f.ts, f.subject, f.predicate, f.key, f.value, f.category, f.confidence "
                        "FROM facts f JOIN facts_fts fts ON f.id = fts.rowid "
                        "WHERE facts_fts MATCH ? AND f.category = ? "
                        "ORDER BY bm25(facts_fts) ASC, f.confidence DESC LIMIT ?",
                        (match, category.strip().lower(), limit),
                    ).fetchall()
                else:
                    rows = self._conn.execute(
                        "SELECT f.id, f.ts, f.subject, f.predicate, f.key, f.value, f.category, f.confidence "
                        "FROM facts f JOIN facts_fts fts ON f.id = fts.rowid "
                        "WHERE facts_fts MATCH ? "
                        "ORDER BY bm25(facts_fts) ASC, f.confidence DESC LIMIT ?",
                        (match, limit),
                    ).fetchall()

                return [
                    {
                        "id": r[0],
                        "ts": r[1],
                        "subject": r[2],
                        "predicate": r[3],
                        "key": r[4],
                        "value": r[5],
                        "category": r[6],
                        "confidence": r[7],
                    }
                    for r in rows
                ]
            except sqlite3.OperationalError:
                return []

    def list_facts(
        self,
        category: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List stored facts ordered by recent update."""
        with self._lock:
            try:
                if category:
                    rows = self._conn.execute(
                        "SELECT id, ts, subject, predicate, key, value, category, confidence, source "
                        "FROM facts WHERE category = ? ORDER BY id DESC LIMIT ?",
                        (category.strip().lower(), limit),
                    ).fetchall()
                else:
                    rows = self._conn.execute(
                        "SELECT id, ts, subject, predicate, key, value, category, confidence, source "
                        "FROM facts ORDER BY id DESC LIMIT ?",
                        (limit,),
                    ).fetchall()

                return [
                    {
                        "id": r[0],
                        "ts": r[1],
                        "subject": r[2],
                        "predicate": r[3],
                        "key": r[4],
                        "value": r[5],
                        "category": r[6],
                        "confidence": r[7],
                        "source": r[8],
                    }
                    for r in rows
                ]
            except sqlite3.OperationalError:
                return []

    def delete_fact(self, key_or_id: str | int) -> bool:
        """Delete a fact by integer ID or by key name."""
        with self._lock:
            try:
                if isinstance(key_or_id, int) or (isinstance(key_or_id, str) and key_or_id.isdigit()):
                    fid = int(key_or_id)
                    row = self._conn.execute("SELECT key, subject FROM facts WHERE id = ?", (fid,)).fetchone()
                    if not row:
                        return False
                    f_key, f_subj = row
                    self._conn.execute("DELETE FROM facts_fts WHERE rowid = ?", (fid,))
                    self._conn.execute("DELETE FROM facts WHERE id = ?", (fid,))
                    if f_subj == "user":
                        self._conn.execute("DELETE FROM user_profile WHERE key = ?", (f_key,))
                    self._conn.commit()
                    return True
                else:
                    target_key = str(key_or_id).strip()
                    rows = self._conn.execute("SELECT id, subject FROM facts WHERE key = ?", (target_key,)).fetchall()
                    if not rows:
                        # Check user_profile
                        self._conn.execute("DELETE FROM user_profile WHERE key = ?", (target_key,))
                        self._conn.commit()
                        return False
                    for fid, f_subj in rows:
                        self._conn.execute("DELETE FROM facts_fts WHERE rowid = ?", (fid,))
                        self._conn.execute("DELETE FROM facts WHERE id = ?", (fid,))
                    self._conn.execute("DELETE FROM user_profile WHERE key = ?", (target_key,))
                    self._conn.commit()
                    return True
            except sqlite3.OperationalError:
                return False

    def get_user_profile(self) -> Dict[str, Any]:
        """Return structured dictionary of the user profile and preferences."""
        with self._lock:
            try:
                rows = self._conn.execute(
                    "SELECT key, value, category, updated_at FROM user_profile ORDER BY category, key"
                ).fetchall()
                profile: Dict[str, Any] = {}
                for key, val, cat, upd in rows:
                    if cat not in profile:
                        profile[cat] = {}
                    profile[cat][key] = val
                return profile
            except sqlite3.OperationalError:
                return {}

    def update_profile_entry(self, key: str, value: str, category: str = "preference") -> None:
        """Set or update a user profile field."""
        self.store_fact(key=key, value=value, category=category, subject="user", predicate="preference")

    def get_memory_summary(self) -> Dict[str, Any]:
        """Return metrics and counts across all memory subsystems."""
        with self._lock:
            try:
                ep_count = self._conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
                ref_count = self._conn.execute("SELECT COUNT(*) FROM reflections").fetchone()[0]
                fact_count = self._conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
                prof_count = self._conn.execute("SELECT COUNT(*) FROM user_profile").fetchone()[0]
                return {
                    "episodes_count": ep_count,
                    "reflections_count": ref_count,
                    "facts_count": fact_count,
                    "profile_keys_count": prof_count,
                    "db_path": str(self.path),
                }
            except sqlite3.OperationalError:
                return {
                    "episodes_count": 0,
                    "reflections_count": 0,
                    "facts_count": 0,
                    "profile_keys_count": 0,
                    "db_path": str(self.path),
                }

    def _trim(self) -> None:
        with self._lock:
            excess = self._conn.execute(
                "SELECT id FROM episodes ORDER BY id DESC LIMIT -1 OFFSET ?", (MAX_EPISODES,)
            ).fetchall()
            if not excess:
                return
            placeholders = ",".join("?" for _ in excess)
            ids = [row[0] for row in excess]
            self._conn.execute(f"DELETE FROM episodes_fts WHERE rowid IN ({placeholders})", ids)  # nosec B608
            self._conn.execute(f"DELETE FROM episodes WHERE id IN ({placeholders})", ids)  # nosec B608
            self._conn.commit()

    def _trim_reflections(self) -> None:
        with self._lock:
            excess = self._conn.execute(
                "SELECT id FROM reflections ORDER BY id DESC LIMIT -1 OFFSET ?", (MAX_REFLECTIONS,)
            ).fetchall()
            if not excess:
                return
            placeholders = ",".join("?" for _ in excess)
            ids = [row[0] for row in excess]
            self._conn.execute(f"DELETE FROM reflections_fts WHERE rowid IN ({placeholders})", ids)  # nosec B608
            self._conn.execute(f"DELETE FROM reflections WHERE id IN ({placeholders})", ids)  # nosec B608
            self._conn.commit()

    def _trim_facts(self) -> None:
        with self._lock:
            excess = self._conn.execute(
                "SELECT id FROM facts ORDER BY id DESC LIMIT -1 OFFSET ?", (MAX_FACTS,)
            ).fetchall()
            if not excess:
                return
            placeholders = ",".join("?" for _ in excess)
            ids = [row[0] for row in excess]
            self._conn.execute(f"DELETE FROM facts_fts WHERE rowid IN ({placeholders})", ids)  # nosec B608
            self._conn.execute(f"DELETE FROM facts WHERE id IN ({placeholders})", ids)  # nosec B608
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()
