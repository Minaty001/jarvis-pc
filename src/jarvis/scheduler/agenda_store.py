"""Persistent SQLite storage for Agenda, Reminders, and Countdown Timers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import datetime
from pathlib import Path
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

from jarvis.system.paths import get_app_paths


@dataclass
class AgendaItem:
    id: Optional[int]
    title: str
    item_type: str  # 'timer', 'reminder', 'event', 'alarm'
    due_timestamp: float
    created_at: float
    status: str  # 'pending', 'completed', 'cancelled'
    recurring: Optional[str] = None  # 'daily', 'weekly', None
    speak_prompt: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        due_dt = datetime.datetime.fromtimestamp(self.due_timestamp)
        d["due_iso"] = due_dt.strftime("%Y-%m-%d %H:%M:%S")
        return d


def _open_agenda_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS agenda_items ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "title TEXT NOT NULL, "
        "item_type TEXT NOT NULL, "
        "due_timestamp REAL NOT NULL, "
        "created_at REAL NOT NULL, "
        "status TEXT NOT NULL, "
        "recurring TEXT, "
        "speak_prompt TEXT)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_agenda_status_due ON agenda_items(status, due_timestamp)"
    )
    conn.commit()
    return conn


class AgendaStore:
    """Thread-safe SQLite store for agenda events and countdown timers."""

    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        if db_path is None:
            db_path = get_app_paths().state / "agenda.db"
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = _open_agenda_db(self.path)

    def add_item(
        self,
        title: str,
        due_timestamp: float,
        item_type: str = "reminder",
        recurring: Optional[str] = None,
        speak_prompt: Optional[str] = None,
    ) -> int:
        """Create a new agenda item or timer."""
        now = time.time()
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO agenda_items (title, item_type, due_timestamp, created_at, status, recurring, speak_prompt) "
                "VALUES (?, ?, ?, ?, 'pending', ?, ?)",
                (title.strip(), item_type.strip().lower(), due_timestamp, now, recurring, speak_prompt),
            )
            self._conn.commit()
            return cur.lastrowid

    def get_item(self, item_id: int) -> Optional[AgendaItem]:
        """Fetch item by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT id, title, item_type, due_timestamp, created_at, status, recurring, speak_prompt "
                "FROM agenda_items WHERE id = ?",
                (item_id,),
            ).fetchone()
            if not row:
                return None
            return AgendaItem(*row)

    def list_items(
        self,
        status: Optional[str] = None,
        item_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[AgendaItem]:
        """List items filtered by status/type."""
        with self._lock:
            query = "SELECT id, title, item_type, due_timestamp, created_at, status, recurring, speak_prompt FROM agenda_items"
            clauses = []
            params: List[Any] = []

            if status:
                clauses.append("status = ?")
                params.append(status.strip().lower())
            if item_type:
                clauses.append("item_type = ?")
                params.append(item_type.strip().lower())

            if clauses:
                query += " WHERE " + " AND ".join(clauses)

            query += " ORDER BY due_timestamp ASC LIMIT ?"
            params.append(limit)

            rows = self._conn.execute(query, params).fetchall()
            return [AgendaItem(*r) for r in rows]

    def get_due_items(self, current_timestamp: Optional[float] = None) -> List[AgendaItem]:
        """Query pending items whose due timestamp has arrived."""
        now = current_timestamp if current_timestamp is not None else time.time()
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, title, item_type, due_timestamp, created_at, status, recurring, speak_prompt "
                "FROM agenda_items WHERE status = 'pending' AND due_timestamp <= ? ORDER BY due_timestamp ASC",
                (now,),
            ).fetchall()
            return [AgendaItem(*r) for r in rows]

    def get_items_for_day(self, target_date: Optional[datetime.date] = None) -> List[AgendaItem]:
        """Query items occurring on a specific calendar date."""
        if target_date is None:
            target_date = datetime.date.today()

        start_dt = datetime.datetime.combine(target_date, datetime.time.min)
        end_dt = datetime.datetime.combine(target_date, datetime.time.max)
        start_ts = start_dt.timestamp()
        end_ts = end_dt.timestamp()

        with self._lock:
            rows = self._conn.execute(
                "SELECT id, title, item_type, due_timestamp, created_at, status, recurring, speak_prompt "
                "FROM agenda_items WHERE due_timestamp >= ? AND due_timestamp <= ? AND status != 'cancelled' "
                "ORDER BY due_timestamp ASC",
                (start_ts, end_ts),
            ).fetchall()
            return [AgendaItem(*r) for r in rows]

    def update_status(self, item_id: int, status: str) -> bool:
        """Update status ('completed', 'cancelled', 'pending')."""
        with self._lock:
            cur = self._conn.execute(
                "UPDATE agenda_items SET status = ? WHERE id = ?",
                (status.strip().lower(), item_id),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def reschedule_recurring(self, item_id: int) -> bool:
        """Advance due timestamp for a recurring item and mark pending."""
        with self._lock:
            item = self.get_item(item_id)
            if not item or not item.recurring:
                return False

            due_dt = datetime.datetime.fromtimestamp(item.due_timestamp)
            if item.recurring == "daily":
                next_dt = due_dt + datetime.timedelta(days=1)
            elif item.recurring == "weekly":
                next_dt = due_dt + datetime.timedelta(weeks=1)
            else:
                return False

            self._conn.execute(
                "UPDATE agenda_items SET due_timestamp = ?, status = 'pending' WHERE id = ?",
                (next_dt.timestamp(), item_id),
            )
            self._conn.commit()
            return True

    def delete_item(self, item_id: int) -> bool:
        """Delete an agenda item by ID."""
        with self._lock:
            cur = self._conn.execute("DELETE FROM agenda_items WHERE id = ?", (item_id,))
            self._conn.commit()
            return cur.rowcount > 0

    def clear_completed(self) -> int:
        """Purge completed or cancelled agenda items."""
        with self._lock:
            cur = self._conn.execute("DELETE FROM agenda_items WHERE status IN ('completed', 'cancelled')")
            self._conn.commit()
            return cur.rowcount

    def close(self) -> None:
        with self._lock:
            self._conn.close()
