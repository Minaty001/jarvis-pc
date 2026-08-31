# JARVIS Task Orchestration System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade JARVIS from a simple command-response assistant into a reliable autonomous multi-action task and daily automation system with durable DAG execution, persistent scheduling, crash recovery, and approval workflows.

**Architecture:** A single canonical `TaskManager` receives all intents from Voice/UI/CLI and decomposes them into persistent `Task` + `TaskStep` DAGs stored in SQLite. A `DurableScheduler` loads jobs from DB on startup so schedules survive restarts. An `ExecutionEngine` runs DAG steps with parallel execution, checkpoints, retry, and approval gates — all deterministic code, LLM only does planning/NL parsing.

**Tech Stack:** Python 3.12, asyncio, SQLite (via `aiosqlite`), Pydantic v2, APScheduler (persistent job store), `dateparser` for NL schedule parsing, existing `tools/registry.py`, `llm/gateway.py`, `voice/pipeline.py`.

**Spec:** This plan implements the 71-section JARVIS upgrade specification submitted by the user on 2026-09-01.

## Global Constraints

- Python ≥ 3.12; use `asyncio` throughout — no threading in execution paths.
- All new modules live under `task_engine/` in the project root.
- Do NOT duplicate existing: `tools/registry.py`, `llm/gateway.py`, `voice/pipeline.py`, `memory/memory_manager.py`, `tools/security.py`.
- Existing `cognitive/orchestrator.py` `_plan()` remains the LLM planner; `TaskManager` calls it.
- Existing `agents/scheduler_agent.py` is superseded and wired to `DurableScheduler` (kept as thin wrapper for compat).
- SQLite DB path: `data/jarvis_tasks.db` (auto-created, gitignored).
- All user-facing strings: plain English, no internal IDs or DAG terms exposed.
- `aiosqlite` must be added to `requirements.txt`; `APScheduler[asyncio]>=3.10`; `dateparser>=1.2`; `croniter>=2.0`.
- Max 3 fix attempts per failing test before escalation.
- Every task ends with `git commit`.

---

## Existing Code Audit Summary

| Module | Keep | Action |
|---|---|---|
| `planning/plan_models.py` — `PlanStep`, `Plan` | ✅ | Extend with new fields; do NOT delete |
| `planning/task_state.py` — `Task`, `TaskStore` | ⚠️ | Replace `TaskStore` in-memory with DB-backed `TaskRepository` |
| `planning/task_planner.py` — `TaskPlanner` | ✅ | Keep; wire into `TaskManager._plan()` |
| `planning/plan_validator.py` — `PlanValidator` | ✅ | Keep; called by `TaskManager` |
| `execution/executor.py` — `StepExecutor` | ✅ | Keep; wrap in `ExecutionEngine` |
| `execution/retry_manager.py` — `RetryManager` | ✅ | Keep; inject into `ExecutionEngine` |
| `execution/critic.py` | ✅ | Keep for verification |
| `agents/scheduler_agent.py` | ⚠️ | Wrap to call `DurableScheduler.add_cron_job()` |
| `memory/memory_manager.py` | ✅ | Keep; add `task_memory` store |
| `proactive/engine.py` | ✅ | Keep; wire to `TaskManager` for suggestions |
| `tools/registry.py` | ✅ | Keep; `TaskManager` queries it |
| `tools/security.py` — `SecurityPolicy` | ✅ | Keep; `ApprovalEngine` calls it |
| `cognitive/orchestrator.py` | ⚠️ | Slim: remove scheduling logic, call `TaskManager` |

---

## File Map

```
task_engine/
  __init__.py
  models.py          ← Task, TaskStep, Schedule, TaskPolicy, ActionResult (Pydantic)
  repository.py      ← SQLite CRUD for tasks, steps, schedules, checkpoints, events
  manager.py         ← TaskManager (single entry point)
  dag_executor.py    ← DAGExecutor (parallel step execution, semaphore)
  scheduler.py       ← DurableScheduler (APScheduler + SQLite job store)
  nl_parser.py       ← NLScheduleParser (dateparser → Schedule)
  approval.py        ← ApprovalEngine (risk gate, pause/resume)
  recovery.py        ← CrashRecovery (startup scan, checkpoint resume)
  routines.py        ← RoutineManager (templates, morning/evening/work)
  conditions.py      ← ConditionEngine (battery, CPU, network triggers)

tests/task_engine/
  test_models.py
  test_repository.py
  test_dag_executor.py
  test_scheduler.py
  test_nl_parser.py
  test_approval.py
  test_recovery.py
  test_routines.py
  test_conditions.py
  test_integration.py

docs/architecture/
  TASK_ORCHESTRATION.md
  MULTI_ACTION_WORKFLOWS.md
  SCHEDULER.md
  MEMORY_AND_ROUTINES.md
  APPROVAL_SYSTEM.md
  RECOVERY_AND_CHECKPOINTS.md

docs/testing/
  TASK_ENGINE_TEST_MATRIX.md
```

---

## Task 1: Core Models (Pydantic)

**Files:**
- Create: `task_engine/__init__.py`
- Create: `task_engine/models.py`
- Create: `tests/task_engine/__init__.py`
- Create: `tests/task_engine/test_models.py`

**Interfaces:**
- Produces: `Task`, `TaskStep`, `Schedule`, `TaskPolicy`, `ActionResult`, `FailureClass`, `TaskPriority`, `StepState`, `TaskState`, `TriggerType`, `MissedPolicy` — all importable from `task_engine.models`

- [ ] **Step 1: Write the failing test**

```python
# tests/task_engine/test_models.py
import pytest
from task_engine.models import (
    Task, TaskStep, Schedule, TaskPolicy, ActionResult,
    TaskState, StepState, TaskPriority, TriggerType, MissedPolicy, FailureClass,
)

def test_task_default_state():
    t = Task(title="Morning briefing", description="Brief me")
    assert t.state == TaskState.DRAFT
    assert t.id.startswith("task-")
    assert t.priority == TaskPriority.NORMAL

def test_task_step_default_state():
    s = TaskStep(task_id="task-abc", name="get_weather", action="get_weather")
    assert s.state == StepState.PENDING
    assert s.attempt_count == 0
    assert s.max_attempts == 3

def test_action_result_success():
    r = ActionResult(success=True, status="COMPLETED", output="done", verified=True)
    assert r.success is True
    assert r.retryable is False

def test_action_result_failure_retryable():
    r = ActionResult(success=False, status="FAILED", error_code=FailureClass.TRANSIENT, retryable=True)
    assert r.retryable is True

def test_schedule_fields():
    s = Schedule(task_id="task-abc", trigger_type=TriggerType.CRON, recurrence="0 8 * * 1-5")
    assert s.enabled is True
    assert s.missed_policy == MissedPolicy.SKIP_IF_MISSED

def test_task_policy_defaults():
    p = TaskPolicy()
    assert p.max_parallel_steps == 4
    assert p.max_total_steps == 50
    assert p.max_retries == 3
```

- [ ] **Step 2: Run test to confirm failure**
```bash
cd /home/shanu/Desktop/Jarvis && .venv/bin/python -m pytest tests/task_engine/test_models.py -v 2>&1 | head -20
```
Expected: `ModuleNotFoundError: No module named 'task_engine'`

- [ ] **Step 3: Create `task_engine/__init__.py` and `task_engine/models.py`**

```python
# task_engine/__init__.py
"""JARVIS Task Orchestration Engine."""
```

```python
# task_engine/models.py
"""Canonical data models for JARVIS Task Orchestration Engine."""
from __future__ import annotations
import uuid, time
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


def _task_id() -> str: return f"task-{uuid.uuid4().hex[:8]}"
def _step_id() -> str: return f"step-{uuid.uuid4().hex[:8]}"
def _sched_id() -> str: return f"sched-{uuid.uuid4().hex[:8]}"
def _now_ts() -> float: return time.time()


class TaskState(str, Enum):
    DRAFT = "DRAFT"
    PLANNED = "PLANNED"
    WAITING = "WAITING"
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    WAITING_FOR_INPUT = "WAITING_FOR_INPUT"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    RETRYING = "RETRYING"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class StepState(str, Enum):
    PENDING = "PENDING"
    WAITING_DEPS = "WAITING_DEPS"
    READY = "READY"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    BLOCKED = "BLOCKED"
    WAITING_APPROVAL = "WAITING_APPROVAL"


class TaskPriority(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"
    BACKGROUND = "BACKGROUND"


class TriggerType(str, Enum):
    ONCE = "ONCE"
    CRON = "CRON"
    INTERVAL = "INTERVAL"
    EVENT = "EVENT"
    CONDITION = "CONDITION"


class MissedPolicy(str, Enum):
    RUN_IF_MISSED = "RUN_IF_MISSED"
    SKIP_IF_MISSED = "SKIP_IF_MISSED"
    RUN_ONCE_AFTER_WAKE = "RUN_ONCE_AFTER_WAKE"
    RESCHEDULE = "RESCHEDULE"


class FailureClass(str, Enum):
    TRANSIENT = "TRANSIENT"
    PERMANENT = "PERMANENT"
    AUTHENTICATION = "AUTHENTICATION"
    PERMISSION = "PERMISSION"
    VALIDATION = "VALIDATION"
    RATE_LIMIT = "RATE_LIMIT"
    NETWORK = "NETWORK"
    TIMEOUT = "TIMEOUT"
    DEPENDENCY = "DEPENDENCY"
    USER_REQUIRED = "USER_REQUIRED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    UNKNOWN = "UNKNOWN"


RETRYABLE_FAILURES = {
    FailureClass.TRANSIENT, FailureClass.RATE_LIMIT,
    FailureClass.NETWORK, FailureClass.TIMEOUT,
}


class ActionResult(BaseModel):
    success: bool = False
    status: str = "PENDING"
    output: Any = None
    error_code: Optional[FailureClass] = None
    error_msg: str = ""
    retryable: bool = False
    metadata: dict = Field(default_factory=dict)
    verified: bool = False

    @classmethod
    def ok(cls, output: Any, verified: bool = True) -> "ActionResult":
        return cls(success=True, status="COMPLETED", output=output, verified=verified, retryable=False)

    @classmethod
    def fail(cls, error_msg: str, error_code: FailureClass = FailureClass.UNKNOWN) -> "ActionResult":
        retryable = error_code in RETRYABLE_FAILURES
        return cls(success=False, status="FAILED", error_msg=error_msg, error_code=error_code, retryable=retryable)


class TaskStep(BaseModel):
    id: str = Field(default_factory=_step_id)
    task_id: str
    name: str
    action: str  # registered tool name or "reason"
    parameters: dict = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)  # list of step ids
    state: StepState = StepState.PENDING
    attempt_count: int = 0
    max_attempts: int = 3
    timeout: float = 60.0
    result: Optional[ActionResult] = None
    error: str = ""
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    required: bool = True  # False = optional step, failure doesn't fail task
    idempotency_key: str = ""

    def is_done(self) -> bool:
        return self.state in (StepState.COMPLETED, StepState.SKIPPED)

    def is_failed(self) -> bool:
        return self.state == StepState.FAILED

    def mark_running(self) -> None:
        self.state = StepState.RUNNING
        self.started_at = time.time()
        self.attempt_count += 1

    def mark_completed(self, result: ActionResult) -> None:
        self.state = StepState.COMPLETED
        self.result = result
        self.completed_at = time.time()

    def mark_failed(self, error: str, result: Optional[ActionResult] = None) -> None:
        self.state = StepState.FAILED
        self.error = error
        self.result = result
        self.completed_at = time.time()


class TaskPolicy(BaseModel):
    max_parallel_steps: int = 4
    max_total_steps: int = 50
    max_runtime: float = 1800.0  # 30 minutes
    max_retries: int = 3
    required_steps: list[str] = Field(default_factory=list)  # step names that must complete
    optional_steps: list[str] = Field(default_factory=list)
    stop_on_first_failure: bool = False  # False = partial success allowed
    approval_required_for: list[str] = Field(default_factory=list)  # tool names needing approval
    missed_schedule_policy: MissedPolicy = MissedPolicy.SKIP_IF_MISSED


class Task(BaseModel):
    id: str = Field(default_factory=_task_id)
    user_id: str = "default"
    title: str
    description: str = ""
    trigger: str = "manual"  # manual / scheduled / event / routine
    priority: TaskPriority = TaskPriority.NORMAL
    state: TaskState = TaskState.DRAFT
    created_at: float = Field(default_factory=_now_ts)
    updated_at: float = Field(default_factory=_now_ts)
    scheduled_at: Optional[float] = None
    deadline: Optional[float] = None
    steps: list[TaskStep] = Field(default_factory=list)
    policy: TaskPolicy = Field(default_factory=TaskPolicy)
    context: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)
    deduplication_key: str = ""
    error: str = ""

    def transition(self, new_state: TaskState) -> None:
        self.state = new_state
        self.updated_at = time.time()

    def completed_steps(self) -> list[TaskStep]:
        return [s for s in self.steps if s.state == StepState.COMPLETED]

    def failed_steps(self) -> list[TaskStep]:
        return [s for s in self.steps if s.state == StepState.FAILED]

    def skipped_steps(self) -> list[TaskStep]:
        return [s for s in self.steps if s.state == StepState.SKIPPED]

    def progress(self) -> float:
        if not self.steps: return 0.0
        done = sum(1 for s in self.steps if s.is_done())
        return done / len(self.steps)

    def is_terminal(self) -> bool:
        return self.state in (
            TaskState.COMPLETED, TaskState.FAILED,
            TaskState.CANCELLED, TaskState.EXPIRED,
        )

    def summary_line(self) -> str:
        done = len(self.completed_steps())
        total = len(self.steps)
        return f"{self.title} [{self.state.value}] {done}/{total} steps"


class Schedule(BaseModel):
    id: str = Field(default_factory=_sched_id)
    task_id: str
    trigger_type: TriggerType = TriggerType.ONCE
    timezone: str = "Asia/Kolkata"
    start_at: Optional[float] = None
    next_run_at: Optional[float] = None
    recurrence: str = ""  # cron expression or interval string
    enabled: bool = True
    max_runs: int = 0  # 0 = unlimited
    run_count: int = 0
    last_run_at: Optional[float] = None
    last_result: str = ""
    missed_policy: MissedPolicy = MissedPolicy.SKIP_IF_MISSED
    raw_nl: str = ""  # original natural language input


class TaskTemplate(BaseModel):
    id: str = Field(default_factory=lambda: f"tmpl-{uuid.uuid4().hex[:8]}")
    name: str
    description: str = ""
    step_blueprints: list[dict] = Field(default_factory=list)
    default_schedule: Optional[str] = None
    variables: dict = Field(default_factory=dict)
    confirmation_policy: str = "auto"
    tags: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Run test to verify pass**
```bash
cd /home/shanu/Desktop/Jarvis && .venv/bin/python -m pytest tests/task_engine/test_models.py -v
```
Expected: 6 tests PASS

- [ ] **Step 5: Commit**
```bash
cd /home/shanu/Desktop/Jarvis && git add task_engine/ tests/task_engine/ && git commit -m "feat(task-engine): Task/TaskStep/Schedule/ActionResult Pydantic models"
```

---

## Task 2: SQLite Repository

**Files:**
- Create: `task_engine/repository.py`
- Modify: `requirements.txt` (add `aiosqlite>=0.19`)
- Create: `tests/task_engine/test_repository.py`

**Interfaces:**
- Consumes: `Task`, `TaskStep`, `Schedule`, `TaskState` from `task_engine.models`
- Produces: `TaskRepository` with CRUD for tasks, schedules, checkpoints, and events

- [ ] **Step 1: Write failing test**
- [ ] **Step 2: Run to confirm failure**
- [ ] **Step 3: Install aiosqlite and write `task_engine/repository.py`**
- [ ] **Step 4: Run test to verify pass**
- [ ] **Step 5: Commit**

---

## Task 3: DAG Executor (Parallel Steps + Semaphore)

**Files:**
- Create: `task_engine/dag_executor.py`
- Create: `tests/task_engine/test_dag_executor.py`

**Interfaces:**
- Consumes: `Task`, `TaskStep`, `TaskPolicy`, `ActionResult`, `StepState` from `task_engine.models`; `TaskRepository` from `task_engine.repository`
- Produces: `DAGExecutor` with method `execute(task: Task, repo: TaskRepository) -> dict`

- [ ] **Step 1: Write failing test**
- [ ] **Step 2: Run to confirm failure**
- [ ] **Step 3: Write `task_engine/dag_executor.py`**
- [ ] **Step 4: Run test to verify pass**
- [ ] **Step 5: Commit**

---

## Task 4: Natural Language Schedule Parser

**Files:**
- Create: `task_engine/nl_parser.py`
- Modify: `requirements.txt` (add `dateparser>=1.2`, `croniter>=2.0`)
- Create: `tests/task_engine/test_nl_parser.py`

**Interfaces:**
- Produces: `NLScheduleParser` with method `parse(text: str, task_id: str, tz: str) -> Schedule`

- [ ] **Step 1: Write failing test**
- [ ] **Step 2: Run to confirm failure**
- [ ] **Step 3: Install deps and write `task_engine/nl_parser.py`**
- [ ] **Step 4: Run test to verify pass**
- [ ] **Step 5: Commit**

---

## Task 5: Durable Scheduler (APScheduler + SQLite Job Store)

**Files:**
- Create: `task_engine/scheduler.py`
- Modify: `requirements.txt` (add `APScheduler[asyncio]>=3.10`)
- Create: `tests/task_engine/test_scheduler.py`

**Interfaces:**
- Produces: `DurableScheduler` with APScheduler backend

- [ ] **Step 1: Write failing test**
- [ ] **Step 2: Run to confirm failure**
- [ ] **Step 3: Install APScheduler and write `task_engine/scheduler.py`**
- [ ] **Step 4: Run test to verify pass**
- [ ] **Step 5: Commit**

---

## Task 6: Approval Engine

**Files:**
- Create: `task_engine/approval.py`
- Create: `tests/task_engine/test_approval.py`

**Interfaces:**
- Produces: `ApprovalEngine` with risk evaluation, request, grant, deny, and timeout mechanisms

- [ ] **Step 1: Write failing test**
- [ ] **Step 2: Run to confirm failure**
- [ ] **Step 3: Write `task_engine/approval.py`**
- [ ] **Step 4: Run test to verify pass**
- [ ] **Step 5: Commit**

---

## Task 7: Crash Recovery

**Files:**
- Create: `task_engine/recovery.py`
- Create: `tests/task_engine/test_recovery.py`

**Interfaces:**
- Produces: `CrashRecovery` with `recover(repo: TaskRepository) -> list[dict]`

- [ ] **Step 1: Write failing test**
- [ ] **Step 2: Run to confirm failure**
- [ ] **Step 3: Write `task_engine/recovery.py`**
- [ ] **Step 4: Run test to verify pass**
- [ ] **Step 5: Commit**

---

## Task 8: Task Manager (Single Entry Point)

**Files:**
- Create: `task_engine/manager.py`
- Create: `tests/task_engine/test_manager.py`

**Interfaces:**
- Produces: `TaskManager` with `submit`, `run_now`, `cancel`, `pause`, `resume`, `status`, `list_tasks`

- [ ] **Step 1: Write failing test**
- [ ] **Step 2: Run to confirm failure**
- [ ] **Step 3: Write `task_engine/manager.py`**
- [ ] **Step 4: Run test to verify pass**
- [ ] **Step 5: Commit**

---

## Task 9: Wire TaskManager into CognitiveOrchestrator and UIBridge

**Files:**
- Modify: `cognitive/orchestrator.py`
- Modify: `ui/bridge.py`
- Modify: `run.py`
- Create: `tests/task_engine/test_integration.py`

- [ ] **Step 1: Write failing integration test**
- [ ] **Step 2: Modify `cognitive/orchestrator.py`**
- [ ] **Step 3: Modify `run.py`**
- [ ] **Step 4: Modify `ui/bridge.py`**
- [ ] **Step 5: Run integration test**
- [ ] **Step 6: Smoke-test JARVIS startup**
- [ ] **Step 7: Commit**

---

## Task 10: Routine Manager

**Files:**
- Create: `task_engine/routines.py`
- Create: `tests/task_engine/test_routines.py`

- [ ] **Step 1: Write failing test**
- [ ] **Step 2: Write `task_engine/routines.py`**
- [ ] **Step 3: Run test to verify pass**
- [ ] **Step 4: Commit**

---

## Task 11: Condition & Event Engine

**Files:**
- Create: `task_engine/conditions.py`
- Create: `tests/task_engine/test_conditions.py`

- [ ] **Step 1: Write failing test**
- [ ] **Step 2: Write `task_engine/conditions.py`**
- [ ] **Step 3: Run test to verify pass**
- [ ] **Step 4: Commit**

---

## Task 12: Documentation

**Files:**
- Create: `docs/architecture/TASK_ORCHESTRATION.md`
- Create: `docs/architecture/MULTI_ACTION_WORKFLOWS.md`
- Create: `docs/architecture/SCHEDULER.md`
- Create: `docs/architecture/MEMORY_AND_ROUTINES.md`
- Create: `docs/architecture/APPROVAL_SYSTEM.md`
- Create: `docs/architecture/RECOVERY_AND_CHECKPOINTS.md`
- Create: `docs/testing/TASK_ENGINE_TEST_MATRIX.md`

- [ ] **Step 1: Write all architecture docs**
- [ ] **Step 2: Commit docs**

---

## Task 13: Final Full Test Run + GitHub Push

- [ ] **Step 1: Run all task_engine tests**
- [ ] **Step 2: Run existing test slices**
- [ ] **Step 3: Smoke test JARVIS boot**
- [ ] **Step 4: Push to GitHub**
