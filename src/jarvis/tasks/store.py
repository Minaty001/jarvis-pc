"""SQLite persistence for JARVIS tasks: goal, plan, step log, artifacts, transcript.

One row per task. JSON columns keep the schema tiny; single-user local use makes
per-column tables overkill. A transcript of every turn (including tool calls) is
stored so a task can be resumed from stored history after a restart.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

_COLS = ("id", "goal", "status", "plan", "steps", "artifacts", "transcript", "created_at", "updated_at")


def _row_to_dict(row: tuple) -> dict[str, Any]:
    task = dict(zip(_COLS, row, strict=True))
    for col in ("plan", "steps", "artifacts", "transcript"):
        task[col] = json.loads(task[col])
    return task


class TaskStore:
    """Persistent record of a JARVIS task: goal, plan, steps, artifacts, transcript."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._lock = threading.RLock()
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id          TEXT PRIMARY KEY,
                    goal        TEXT NOT NULL DEFAULT '',
                    status      TEXT NOT NULL DEFAULT 'open',
                    plan        TEXT NOT NULL DEFAULT '[]',
                    steps       TEXT NOT NULL DEFAULT '[]',
                    artifacts   TEXT NOT NULL DEFAULT '{}',
                    transcript  TEXT NOT NULL DEFAULT '[]',
                    created_at  INTEGER NOT NULL,
                    updated_at  INTEGER NOT NULL
                )
                """
            )
            self._conn.commit()

    def create(self, task_id: str | None = None, goal: str = "") -> str:
        """Create a task, or return the existing id if it already exists (idempotent resume)."""
        task_id = task_id or uuid.uuid4().hex[:8]
        now = int(time.time())
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO tasks VALUES (?,?,?,?,?,?,?,?,?)",
                (task_id, goal, "open", "[]", "[]", "{}", "[]", now, now),
            )
            self._conn.commit()
        return task_id

    def get(self, task_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return _row_to_dict(row) if row else None

    def list_tasks(self, status: str | None = None) -> list[dict[str, Any]]:
        if status:
            query = "SELECT * FROM tasks WHERE status = ?"
            args: tuple[Any, ...] = (status,)
        else:
            query = "SELECT * FROM tasks"
            args = ()
        with self._lock:
            rows = self._conn.execute(query, args).fetchall()
        return [_row_to_dict(row) for row in rows]

    _JSON_COLS = ("plan", "steps", "artifacts", "transcript")

    def _set(self, task_id: str, **fields: Any) -> bool:
        if not fields:
            return True
        for col in fields:
            if col not in _COLS:
                raise ValueError(f"Invalid column: {col}")
        assignments = ", ".join(f"{col} = ?" for col in fields)
        values = [
            json.dumps(value) if col in self._JSON_COLS else value
            for col, value in fields.items()
        ]
        values.extend((int(time.time()), task_id))
        with self._lock:
            cur = self._conn.execute(
                f"UPDATE tasks SET {assignments}, updated_at = ? WHERE id = ?", values  # nosec B608
            )
            self._conn.commit()
        return cur.rowcount > 0

    def set_status(self, task_id: str, status: str) -> bool:
        return self._set(task_id, status=status)

    def set_plan(self, task_id: str, plan: list[str]) -> bool:
        return self._set(task_id, plan=plan)

    def set_transcript(self, task_id: str, transcript: list[dict[str, Any]]) -> bool:
        """Persist the exact LLM message dicts (user/assistant/tool) for resumability."""
        return self._set(task_id, transcript=transcript)

    def close(self) -> None:
        self._conn.close()