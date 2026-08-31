# JARVIS Task Orchestration Architecture

## Overview
All user requests flow through a single canonical entry point: `TaskManager` → `Task` + `TaskStep` (DAG) → `DAGExecutor` → Tool Registry → Results & Persistence.

```
Voice / UI / CLI Intent
       │
       ▼
  TaskManager.submit(goal, schedule_nl)
       │
       ├── Schedule? ──► DurableScheduler (APScheduler + SQLite)
       │
       ▼
  Task + Steps (DAG)
       │
       ├── Security / Approval Gate? ──► ApprovalEngine (Human confirmation)
       │
       ▼
  DAGExecutor.execute()
       ├── Parallel Steps (Semaphore limit)
       ├── Checkpoints after each step ──► SQLite (task_checkpoints)
       └── Event Log ──► SQLite (task_events)
```

## Core Modules
- **`TaskManager`** (`task_engine/manager.py`): Primary control point for task submission, manual triggering, pause, resume, cancel, and approval decisions.
- **`DAGExecutor`** (`task_engine/dag_executor.py`): Dependency graph execution engine. Resolves prerequisites, runs independent steps concurrently using an asyncio semaphore, and automatically skips dependent steps if a required parent step fails.
- **`TaskRepository`** (`task_engine/repository.py`): Async SQLite database driver managing tasks, schedules, checkpoints, and event logs.
- **`DurableScheduler`** (`task_engine/scheduler.py`): Wraps APScheduler; syncs schedule definitions with SQLite on startup so recurring and scheduled tasks survive app restarts.
- **`ApprovalEngine`** (`task_engine/approval.py`): Risk-based gate intercepting high-risk or destructive actions for explicit human approval.
- **`CrashRecovery`** (`task_engine/recovery.py`): Startup scanner that resumes interrupted tasks from their last completed step checkpoint.
- **`RoutineManager`** (`task_engine/routines.py`): Pre-configured task templates for morning briefings, work setup, evening summaries, and night routines.
- **`ConditionEngine`** (`task_engine/conditions.py`): Event- and metric-driven task triggers for battery level, CPU load, and user activity.
