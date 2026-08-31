# tests/task_engine/test_repository.py
import asyncio, pytest
from task_engine.models import Task, TaskState, Schedule, TriggerType, TaskStep
from task_engine.repository import TaskRepository

DB_PATH = ":memory:"

@pytest.fixture
def repo():
    r = TaskRepository(db_path=DB_PATH)
    asyncio.get_event_loop().run_until_complete(r.initialize())
    return r

def test_create_and_get_task(repo):
    task = Task(title="Test task", description="desc")
    asyncio.get_event_loop().run_until_complete(repo.create_task(task))
    loaded = asyncio.get_event_loop().run_until_complete(repo.get_task(task.id))
    assert loaded is not None
    assert loaded.title == "Test task"
    assert loaded.state == TaskState.DRAFT

def test_update_task_state(repo):
    task = Task(title="Update test")
    asyncio.get_event_loop().run_until_complete(repo.create_task(task))
    task.transition(TaskState.RUNNING)
    asyncio.get_event_loop().run_until_complete(repo.update_task(task))
    loaded = asyncio.get_event_loop().run_until_complete(repo.get_task(task.id))
    assert loaded.state == TaskState.RUNNING

def test_list_tasks_by_state(repo):
    t1 = Task(title="T1"); t1.transition(TaskState.RUNNING)
    t2 = Task(title="T2"); t2.transition(TaskState.COMPLETED)
    asyncio.get_event_loop().run_until_complete(repo.create_task(t1))
    asyncio.get_event_loop().run_until_complete(repo.create_task(t2))
    running = asyncio.get_event_loop().run_until_complete(repo.list_tasks(state=TaskState.RUNNING))
    assert len(running) >= 1
    assert all(t.state == TaskState.RUNNING for t in running)

def test_save_and_get_schedule(repo):
    sched = Schedule(task_id="task-abc", trigger_type=TriggerType.CRON, recurrence="0 8 * * *")
    asyncio.get_event_loop().run_until_complete(repo.save_schedule(sched))
    loaded = asyncio.get_event_loop().run_until_complete(repo.get_schedule(sched.id))
    assert loaded is not None
    assert loaded.recurrence == "0 8 * * *"

def test_checkpoint_roundtrip(repo):
    data = {"last_completed_step": "step-1", "output": "weather ok"}
    asyncio.get_event_loop().run_until_complete(repo.save_checkpoint("task-abc", "step-1", data))
    loaded = asyncio.get_event_loop().run_until_complete(repo.get_checkpoint("task-abc", "step-1"))
    assert loaded["last_completed_step"] == "step-1"

def test_append_event(repo):
    asyncio.get_event_loop().run_until_complete(
        repo.append_event("task-abc", "TASK_CREATED", {"goal": "test"})
    )
    events = asyncio.get_event_loop().run_until_complete(repo.list_events("task-abc"))
    assert len(events) == 1
    assert events[0]["event_type"] == "TASK_CREATED"
