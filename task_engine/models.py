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
