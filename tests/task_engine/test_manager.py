# tests/task_engine/test_manager.py
import asyncio, pytest
from unittest.mock import AsyncMock, MagicMock, patch
from task_engine.manager import TaskManager
from task_engine.models import TaskState, StepState

@pytest.fixture
def manager():
    mgr = TaskManager()
    mgr._repo = AsyncMock()
    mgr._repo.create_task = AsyncMock()
    mgr._repo.get_task = AsyncMock(return_value=None)
    mgr._repo.update_task = AsyncMock()
    mgr._repo.list_tasks = AsyncMock(return_value=[])
    mgr._repo.list_schedules = AsyncMock(return_value=[])
    mgr._repo.append_event = AsyncMock()
    mgr._repo.save_checkpoint = AsyncMock()
    mgr._repo.list_checkpoints = AsyncMock(return_value=[])
    return mgr

def test_submit_creates_task(manager):
    task = asyncio.get_event_loop().run_until_complete(
        manager.submit("Play pi loon on YouTube")
    )
    assert task.id.startswith("task-")
    assert task.title == "Play pi loon on YouTube"

def test_submit_with_schedule(manager):
    manager._scheduler = MagicMock()
    manager._scheduler.add_schedule = MagicMock(return_value="job-1")
    task = asyncio.get_event_loop().run_until_complete(
        manager.submit("Daily briefing", schedule_nl="every weekday at 8 AM")
    )
    assert task.state in (TaskState.DRAFT, TaskState.PLANNED)

def test_cancel_task(manager):
    from task_engine.models import Task
    task = Task(title="T1")
    manager._repo.get_task = AsyncMock(return_value=task)
    asyncio.get_event_loop().run_until_complete(manager.cancel(task.id))
    assert task.state == TaskState.CANCELLED

def test_status_returns_dict(manager):
    from task_engine.models import Task
    task = Task(title="T1")
    manager._repo.get_task = AsyncMock(return_value=task)
    status = asyncio.get_event_loop().run_until_complete(manager.status(task.id))
    assert "state" in status
    assert "progress" in status

def test_grant_approval_forwards(manager):
    manager._approval = MagicMock()
    manager._approval.grant = MagicMock()
    asyncio.get_event_loop().run_until_complete(manager.grant_approval("appr-123"))
    manager._approval.grant.assert_called_once_with("appr-123")
