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
