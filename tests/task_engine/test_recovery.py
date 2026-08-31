# tests/task_engine/test_recovery.py
import asyncio, pytest
from unittest.mock import AsyncMock
from task_engine.models import Task, TaskStep, TaskState, StepState
from task_engine.recovery import CrashRecovery

def _repo_with_tasks(tasks):
    repo = AsyncMock()
    repo.list_tasks = AsyncMock(return_value=tasks)
    repo.list_checkpoints = AsyncMock(return_value=[])
    repo.update_task = AsyncMock()
    repo.append_event = AsyncMock()
    return repo

def test_running_task_gets_recovered():
    task = Task(title="T1")
    task.transition(TaskState.RUNNING)
    task.steps = [
        TaskStep(task_id=task.id, name="s1", action="weather", state=StepState.COMPLETED),
        TaskStep(task_id=task.id, name="s2", action="summary", state=StepState.RUNNING),
    ]
    repo = _repo_with_tasks([task])
    recovery = CrashRecovery()
    actions = asyncio.get_event_loop().run_until_complete(recovery.recover(repo))
    assert any(a["action"] in ("resume", "ask_user") for a in actions)

def test_completed_task_not_recovered():
    task = Task(title="T2")
    task.transition(TaskState.COMPLETED)
    repo = _repo_with_tasks([task])
    recovery = CrashRecovery()
    actions = asyncio.get_event_loop().run_until_complete(recovery.recover(repo))
    assert not any(a["task_id"] == task.id for a in actions)

def test_waiting_approval_task_flagged():
    task = Task(title="T3")
    task.transition(TaskState.WAITING_FOR_APPROVAL)
    repo = _repo_with_tasks([task])
    recovery = CrashRecovery()
    actions = asyncio.get_event_loop().run_until_complete(recovery.recover(repo))
    act = next((a for a in actions if a["task_id"] == task.id), None)
    assert act is not None
    assert act["action"] == "ask_user"
