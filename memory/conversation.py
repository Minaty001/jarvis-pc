"""
Conversation History Store.
SQLite-based conversation persistence.
"""

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Optional

from config.logger import get_logger
from config.settings import settings

logger = get_logger("memory.conversation")

DB_PATH = settings.data_dir / "conversations.db"


class ConversationStore:
    """SQLite-backed conversation history."""

    def __init__(self):
        self._local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(DB_PATH))
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_session ON messages(session_id, timestamp);
        """)
        conn.commit()

    def record(self, session_id: str, role: str, content: str) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, role, content, time.time()),
        )
        conn.commit()

    def get_history(self, session_id: str, limit: int = 20) -> list[dict[str, Any]]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT role, content, timestamp FROM messages WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
        return [{"role": r["role"], "content": r["content"], "timestamp": r["timestamp"]} for r in reversed(rows)]

    def clear_session(self, session_id: str) -> int:
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.commit()
        return cursor.rowcount

    def sessions(self) -> list[str]:
        conn = self._get_conn()
        rows = conn.execute("SELECT DISTINCT session_id FROM messages").fetchall()
        return [r["session_id"] for r in rows]


conversation_store = ConversationStore()
