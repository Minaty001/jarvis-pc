"""SQLite FTS5 Knowledge Store for full-text semantic document and code retrieval."""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def default_knowledge_db_path() -> Path:
    """Return default knowledge database location."""
    base = os.environ.get("JARVIS_DATA_DIR", os.path.expanduser("~/.local/share/jarvis"))
    return Path(base) / "knowledge.db"


def _open_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")

    # Files table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS indexed_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE NOT NULL,
            file_hash TEXT NOT NULL,
            mtime REAL NOT NULL,
            size INTEGER NOT NULL,
            chunks_count INTEGER NOT NULL DEFAULT 0,
            indexed_at INTEGER NOT NULL
        )
        """
    )

    # Chunks table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            path TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            start_line INTEGER NOT NULL,
            end_line INTEGER NOT NULL,
            category TEXT NOT NULL,
            content TEXT NOT NULL,
            FOREIGN KEY(file_id) REFERENCES indexed_files(id) ON DELETE CASCADE
        )
        """
    )

    # Full text index (FTS5)
    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            content,
            path,
            category,
            content='knowledge_chunks',
            content_rowid='id'
        )
        """
    )

    conn.commit()
    return conn


class KnowledgeStore:
    """Thread-safe SQLite FTS5 knowledge store."""

    def __init__(self, path: Optional[str | Path] = None):
        self.path = Path(path) if path else default_knowledge_db_path()
        self._lock = threading.RLock()
        self._conn = _open_db(self.path)

    def add_or_update_file(
        self,
        path: str,
        file_hash: str,
        mtime: float,
        size: int,
        chunks: List[Dict[str, Any]],
    ) -> int:
        """Insert or replace indexed file record and all its text chunks."""
        clean_path = str(Path(path).resolve())
        now = int(time.time())

        with self._lock:
            # Delete previous chunks and record if exists
            row = self._conn.execute(
                "SELECT id FROM indexed_files WHERE path = ?", (clean_path,)
            ).fetchone()
            if row:
                file_id = row[0]
                self._conn.execute("DELETE FROM chunks_fts WHERE rowid IN (SELECT id FROM knowledge_chunks WHERE file_id = ?)", (file_id,))
                self._conn.execute("DELETE FROM knowledge_chunks WHERE file_id = ?", (file_id,))
                self._conn.execute(
                    "UPDATE indexed_files SET file_hash = ?, mtime = ?, size = ?, chunks_count = ?, indexed_at = ? WHERE id = ?",
                    (file_hash, mtime, size, len(chunks), now, file_id),
                )
            else:
                cur = self._conn.execute(
                    "INSERT INTO indexed_files (path, file_hash, mtime, size, chunks_count, indexed_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (clean_path, file_hash, mtime, size, len(chunks), now),
                )
                file_id = cur.lastrowid

            # Insert chunks
            for idx, chunk in enumerate(chunks):
                content = chunk.get("content", "").strip()
                if not content:
                    continue
                start_l = chunk.get("start_line", 1)
                end_l = chunk.get("end_line", 1)
                cat = chunk.get("category", "text")

                c_cur = self._conn.execute(
                    "INSERT INTO knowledge_chunks (file_id, path, chunk_index, start_line, end_line, category, content) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (file_id, clean_path, idx, start_l, end_l, cat, content),
                )
                chunk_rowid = c_cur.lastrowid
                self._conn.execute(
                    "INSERT INTO chunks_fts (rowid, content, path, category) VALUES (?, ?, ?, ?)",
                    (chunk_rowid, content, clean_path, cat),
                )

            self._conn.commit()
            return file_id

    def delete_file(self, path: str) -> bool:
        """Remove file and its chunks from knowledge store."""
        clean_path = str(Path(path).resolve())
        with self._lock:
            row = self._conn.execute("SELECT id FROM indexed_files WHERE path = ?", (clean_path,)).fetchone()
            if not row:
                return False
            file_id = row[0]
            self._conn.execute("DELETE FROM chunks_fts WHERE rowid IN (SELECT id FROM knowledge_chunks WHERE file_id = ?)", (file_id,))
            self._conn.execute("DELETE FROM knowledge_chunks WHERE file_id = ?", (file_id,))
            self._conn.execute("DELETE FROM indexed_files WHERE id = ?", (file_id,))
            self._conn.commit()
            return True

    def get_file_info(self, path: str) -> Optional[Dict[str, Any]]:
        """Get file indexing metadata."""
        clean_path = str(Path(path).resolve())
        with self._lock:
            row = self._conn.execute(
                "SELECT id, path, file_hash, mtime, size, chunks_count, indexed_at FROM indexed_files WHERE path = ?",
                (clean_path,),
            ).fetchone()
            if not row:
                return None
            return {
                "id": row[0],
                "path": row[1],
                "file_hash": row[2],
                "mtime": row[3],
                "size": row[4],
                "chunks_count": row[5],
                "indexed_at": row[6],
            }

    def list_files(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List all currently indexed files."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, path, file_hash, mtime, size, chunks_count, indexed_at FROM indexed_files ORDER BY indexed_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [
                {
                    "id": r[0],
                    "path": r[1],
                    "file_hash": r[2],
                    "mtime": r[3],
                    "size": r[4],
                    "chunks_count": r[5],
                    "indexed_at": r[6],
                }
                for r in rows
            ]

    def search(
        self,
        query: str,
        limit: int = 5,
        file_pattern: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Perform BM25 search across all indexed chunks."""
        terms = [t for t in query.split() if t]
        if not terms:
            return []

        escaped_terms = [t.replace('"', '""') for t in terms]
        match_expr = " OR ".join(f'"{t}"' for t in escaped_terms)

        with self._lock:
            try:
                if file_pattern:
                    sql = (
                        "SELECT c.id, c.path, c.chunk_index, c.start_line, c.end_line, c.category, c.content, bm25(chunks_fts) as rank "
                        "FROM knowledge_chunks c "
                        "JOIN chunks_fts fts ON c.id = fts.rowid "
                        "WHERE chunks_fts MATCH ? AND c.path LIKE ? "
                        "ORDER BY rank ASC LIMIT ?"
                    )
                    pattern_param = f"%{file_pattern}%"
                    rows = self._conn.execute(sql, (match_expr, pattern_param, limit)).fetchall()
                else:
                    sql = (
                        "SELECT c.id, c.path, c.chunk_index, c.start_line, c.end_line, c.category, c.content, bm25(chunks_fts) as rank "
                        "FROM knowledge_chunks c "
                        "JOIN chunks_fts fts ON c.id = fts.rowid "
                        "WHERE chunks_fts MATCH ? "
                        "ORDER BY rank ASC LIMIT ?"
                    )
                    rows = self._conn.execute(sql, (match_expr, limit)).fetchall()

                return [
                    {
                        "chunk_id": r[0],
                        "path": r[1],
                        "chunk_index": r[2],
                        "start_line": r[3],
                        "end_line": r[4],
                        "category": r[5],
                        "content": r[6],
                        "score": round(float(r[7]), 4),
                    }
                    for r in rows
                ]
            except sqlite3.OperationalError as exc:
                logger.debug("Knowledge FTS search query error (%s): %s", match_expr, exc)
                return []

    def get_stats(self) -> Dict[str, Any]:
        """Return knowledge store counts and metrics."""
        with self._lock:
            files_count = self._conn.execute("SELECT COUNT(*) FROM indexed_files").fetchone()[0]
            chunks_count = self._conn.execute("SELECT COUNT(*) FROM knowledge_chunks").fetchone()[0]
            total_bytes = self._conn.execute("SELECT COALESCE(SUM(size), 0) FROM indexed_files").fetchone()[0]
            return {
                "total_files": files_count,
                "total_chunks": chunks_count,
                "total_bytes": total_bytes,
                "db_path": str(self.path),
            }

    def clear(self) -> None:
        """Clear all knowledge index tables."""
        with self._lock:
            self._conn.execute("DELETE FROM chunks_fts")
            self._conn.execute("DELETE FROM knowledge_chunks")
            self._conn.execute("DELETE FROM indexed_files")
            self._conn.commit()

    def close(self) -> None:
        """Close connection."""
        with self._lock:
            self._conn.close()
