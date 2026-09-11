"""Persistent SQLite store for swarm tasks and subagent logs."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from jarvis.swarm.models import SwarmTask, TaskStatus, WorkerRole
from jarvis.system.paths import get_app_paths

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = get_app_paths().state / "swarm.db"


class SwarmStore:
    """Thread-safe SQLite store for Swarm tasks and execution logs."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else _DEFAULT_DB_PATH
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS swarm_tasks (
                    id TEXT PRIMARY KEY,
                    parent_goal TEXT,
                    role TEXT,
                    instruction TEXT,
                    name TEXT,
                    status TEXT,
                    result TEXT,
                    error TEXT,
                    progress_percent INTEGER,
                    created_at TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    logs TEXT,
                    metadata TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_swarm_status ON swarm_tasks(status)")
            conn.commit()

    def save_task(self, task: SwarmTask) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO swarm_tasks (
                    id, parent_goal, role, instruction, name, status,
                    result, error, progress_percent, created_at, started_at,
                    completed_at, logs, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.id,
                    task.parent_goal,
                    task.role.value if isinstance(task.role, WorkerRole) else str(task.role),
                    task.instruction,
                    task.name,
                    task.status.value if isinstance(task.status, TaskStatus) else str(task.status),
                    task.result,
                    task.error,
                    task.progress_percent,
                    task.created_at,
                    task.started_at,
                    task.completed_at,
                    json.dumps(task.logs),
                    json.dumps(task.metadata),
                ),
            )
            conn.commit()

    def get_task(self, task_id: str) -> Optional[SwarmTask]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM swarm_tasks WHERE id = ?", (task_id,)).fetchone()
            if not row:
                return None
            return self._row_to_task(row)

    def list_tasks(
        self,
        status: Optional[str | TaskStatus] = None,
        role: Optional[str | WorkerRole] = None,
        limit: int = 50,
    ) -> List[SwarmTask]:
        query = "SELECT * FROM swarm_tasks WHERE 1=1"
        params: List[Any] = []

        if status:
            val = status.value if isinstance(status, TaskStatus) else str(status)
            query += " AND status = ?"
            params.append(val)

        if role:
            val = role.value if isinstance(role, WorkerRole) else str(role)
            query += " AND role = ?"
            params.append(val)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_task(r) for r in rows]

    def delete_task(self, task_id: str) -> bool:
        with self._get_connection() as conn:
            cur = conn.execute("DELETE FROM swarm_tasks WHERE id = ?", (task_id,))
            conn.commit()
            return cur.rowcount > 0

    def clear_tasks(self) -> int:
        with self._get_connection() as conn:
            cur = conn.execute("DELETE FROM swarm_tasks")
            conn.commit()
            return cur.rowcount

    def _row_to_task(self, row: sqlite3.Row) -> SwarmTask:
        logs_raw = row["logs"]
        logs = json.loads(logs_raw) if logs_raw else []
        metadata_raw = row["metadata"]
        metadata = json.loads(metadata_raw) if metadata_raw else {}

        return SwarmTask(
            id=row["id"],
            parent_goal=row["parent_goal"] or "",
            role=WorkerRole(row["role"]) if row["role"] in [r.value for r in WorkerRole] else WorkerRole.GENERAL,
            instruction=row["instruction"] or "",
            name=row["name"] or "",
            status=TaskStatus(row["status"]) if row["status"] in [s.value for s in TaskStatus] else TaskStatus.PENDING,
            result=row["result"] or "",
            error=row["error"],
            progress_percent=row["progress_percent"] or 0,
            created_at=row["created_at"] or "",
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            logs=logs,
            metadata=metadata,
        )
