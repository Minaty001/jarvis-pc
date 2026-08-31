# task_engine/repository.py
"""SQLite-backed persistence for tasks, schedules, checkpoints, and events."""
from __future__ import annotations
import json, time
from typing import Optional
import aiosqlite
from config.logger import get_logger
from task_engine.models import Task, TaskState, Schedule, TaskStep

logger = get_logger("task_engine.repository")

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    state TEXT NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS schedules (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    data TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    next_run_at REAL
);
CREATE TABLE IF NOT EXISTS checkpoints (
    task_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    data TEXT NOT NULL,
    saved_at REAL NOT NULL,
    PRIMARY KEY (task_id, step_id)
);
CREATE TABLE IF NOT EXISTS task_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    data TEXT NOT NULL,
    timestamp REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tasks_state ON tasks(state);
CREATE INDEX IF NOT EXISTS idx_events_task ON task_events(task_id);
CREATE INDEX IF NOT EXISTS idx_schedules_next ON schedules(next_run_at, enabled);
"""


class TaskRepository:
    """Async SQLite repository for all task engine data."""

    def __init__(self, db_path: str = "data/jarvis_tasks.db"):
        self.db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None

    async def initialize(self) -> None:
        if self.db_path != ":memory:":
            import os; os.makedirs("data", exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(SCHEMA)
        await self._db.commit()
        logger.info("TaskRepository initialized at %s", self.db_path)

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    # ── Tasks ────────────────────────────────────────────────────────────────

    async def create_task(self, task: Task) -> None:
        await self._db.execute(
            "INSERT INTO tasks(id, data, state, updated_at) VALUES(?,?,?,?)",
            (task.id, task.model_dump_json(), task.state.value, task.updated_at),
        )
        await self._db.commit()

    async def get_task(self, task_id: str) -> Optional[Task]:
        async with self._db.execute("SELECT data FROM tasks WHERE id=?", (task_id,)) as cur:
            row = await cur.fetchone()
        if not row: return None
        return Task.model_validate_json(row["data"])

    async def update_task(self, task: Task) -> None:
        await self._db.execute(
            "UPDATE tasks SET data=?, state=?, updated_at=? WHERE id=?",
            (task.model_dump_json(), task.state.value, task.updated_at, task.id),
        )
        await self._db.commit()

    async def list_tasks(self, state: Optional[TaskState] = None) -> list[Task]:
        if state:
            async with self._db.execute(
                "SELECT data FROM tasks WHERE state=? ORDER BY updated_at DESC", (state.value,)
            ) as cur:
                rows = await cur.fetchall()
        else:
            async with self._db.execute(
                "SELECT data FROM tasks ORDER BY updated_at DESC"
            ) as cur:
                rows = await cur.fetchall()
        return [Task.model_validate_json(r["data"]) for r in rows]

    # ── Schedules ────────────────────────────────────────────────────────────

    async def save_schedule(self, sched: Schedule) -> None:
        await self._db.execute(
            "INSERT OR REPLACE INTO schedules(id, task_id, data, enabled, next_run_at) VALUES(?,?,?,?,?)",
            (sched.id, sched.task_id, sched.model_dump_json(), int(sched.enabled), sched.next_run_at),
        )
        await self._db.commit()

    async def get_schedule(self, sched_id: str) -> Optional[Schedule]:
        async with self._db.execute(
            "SELECT data FROM schedules WHERE id=?", (sched_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row: return None
        return Schedule.model_validate_json(row["data"])

    async def list_schedules(self, enabled_only: bool = True) -> list[Schedule]:
        q = "SELECT data FROM schedules" + (" WHERE enabled=1" if enabled_only else "")
        async with self._db.execute(q) as cur:
            rows = await cur.fetchall()
        return [Schedule.model_validate_json(r["data"]) for r in rows]

    async def delete_schedule(self, sched_id: str) -> None:
        await self._db.execute("DELETE FROM schedules WHERE id=?", (sched_id,))
        await self._db.commit()

    # ── Checkpoints ──────────────────────────────────────────────────────────

    async def save_checkpoint(self, task_id: str, step_id: str, data: dict) -> None:
        await self._db.execute(
            "INSERT OR REPLACE INTO checkpoints(task_id, step_id, data, saved_at) VALUES(?,?,?,?)",
            (task_id, step_id, json.dumps(data), time.time()),
        )
        await self._db.commit()

    async def get_checkpoint(self, task_id: str, step_id: str) -> Optional[dict]:
        async with self._db.execute(
            "SELECT data FROM checkpoints WHERE task_id=? AND step_id=?", (task_id, step_id)
        ) as cur:
            row = await cur.fetchone()
        if not row: return None
        return json.loads(row["data"])

    async def list_checkpoints(self, task_id: str) -> list[dict]:
        async with self._db.execute(
            "SELECT step_id, data, saved_at FROM checkpoints WHERE task_id=? ORDER BY saved_at",
            (task_id,)
        ) as cur:
            rows = await cur.fetchall()
        return [{"step_id": r["step_id"], **json.loads(r["data"]), "saved_at": r["saved_at"]} for r in rows]

    # ── Events ───────────────────────────────────────────────────────────────

    async def append_event(self, task_id: str, event_type: str, data: dict) -> None:
        await self._db.execute(
            "INSERT INTO task_events(task_id, event_type, data, timestamp) VALUES(?,?,?,?)",
            (task_id, event_type, json.dumps(data), time.time()),
        )
        await self._db.commit()

    async def list_events(self, task_id: str, limit: int = 200) -> list[dict]:
        async with self._db.execute(
            "SELECT event_type, data, timestamp FROM task_events WHERE task_id=? ORDER BY timestamp LIMIT ?",
            (task_id, limit)
        ) as cur:
            rows = await cur.fetchall()
        return [{"event_type": r["event_type"], "timestamp": r["timestamp"], **json.loads(r["data"])} for r in rows]


task_repository = TaskRepository()
