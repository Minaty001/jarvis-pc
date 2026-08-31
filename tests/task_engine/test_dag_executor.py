# tests/task_engine/test_dag_executor.py
import asyncio, pytest
from unittest.mock import AsyncMock, MagicMock
from task_engine.models import Task, TaskStep, TaskPolicy, StepState, ActionResult
from task_engine.dag_executor import DAGExecutor
from task_engine.repository import TaskRepository

def _make_task(*actions):
    task = Task(title="Test DAG")
    steps = []
    for i, action in enumerate(actions):
        s = TaskStep(task_id=task.id, name=f"step-{i}", action=action)
        if i > 0:
            s.dependencies = [steps[i-1].id]
        steps.append(s)
    task.steps = steps
    return task

def test_linear_dag_all_complete():
    """Steps run sequentially when each depends on the previous."""
    repo = AsyncMock(spec=TaskRepository)
    repo.save_checkpoint = AsyncMock()
    repo.append_event = AsyncMock()
    repo.update_task = AsyncMock()

    async def fake_exec(tool, params):
        return ActionResult.ok(f"done:{tool}")

    executor = DAGExecutor(step_runner=fake_exec)
    task = _make_task("weather", "summarize")
    result = asyncio.get_event_loop().run_until_complete(executor.execute(task, repo))
    assert result["completed"] == 2
    assert result["failed"] == 0

def test_independent_steps_run_in_parallel():
    """Steps with no dependencies run concurrently."""
    call_times = []

    async def slow_exec(tool, params):
        import time; t = time.monotonic(); call_times.append(t)
        await asyncio.sleep(0.05)
        return ActionResult.ok(f"done:{tool}")

    executor = DAGExecutor(step_runner=slow_exec, max_parallel=4)
    task = Task(title="Parallel test")
    task.steps = [
        TaskStep(task_id=task.id, name=f"s{i}", action=f"tool_{i}")
        for i in range(4)
    ]
    repo = AsyncMock(spec=TaskRepository)
    repo.save_checkpoint = AsyncMock()
    repo.append_event = AsyncMock()
    repo.update_task = AsyncMock()

    import time
    start = time.monotonic()
    result = asyncio.get_event_loop().run_until_complete(executor.execute(task, repo))
    elapsed = time.monotonic() - start
    assert result["completed"] == 4
    assert elapsed < 0.3  # 4 parallel 50ms tasks should finish in <300ms

def test_failed_step_marks_dependents_skipped():
    """When a required step fails, dependent steps are skipped."""
    async def fail_first(tool, params):
        if tool == "weather":
            return ActionResult.fail("network error")
        return ActionResult.ok("ok")

    executor = DAGExecutor(step_runner=fail_first)
    task = Task(title="Failure test")
    s1 = TaskStep(task_id=task.id, name="weather", action="weather")
    s2 = TaskStep(task_id=task.id, name="summary", action="summary", dependencies=[s1.id])
    task.steps = [s1, s2]
    repo = AsyncMock(spec=TaskRepository)
    repo.save_checkpoint = AsyncMock()
    repo.append_event = AsyncMock()
    repo.update_task = AsyncMock()

    result = asyncio.get_event_loop().run_until_complete(executor.execute(task, repo))
    assert result["failed"] == 1
    assert result["skipped"] == 1

def test_optional_step_failure_doesnt_block():
    """Optional step failure does not block dependents or fail the task."""
    async def fail_email(tool, params):
        if tool == "email":
            return ActionResult.fail("auth error")
        return ActionResult.ok("ok")

    executor = DAGExecutor(step_runner=fail_email)
    task = Task(title="Optional failure test")
    s1 = TaskStep(task_id=task.id, name="email", action="email", required=False)
    s2 = TaskStep(task_id=task.id, name="summary", action="summary")  # no dep on email
    task.steps = [s1, s2]
    repo = AsyncMock(spec=TaskRepository)
    repo.save_checkpoint = AsyncMock()
    repo.append_event = AsyncMock()
    repo.update_task = AsyncMock()

    result = asyncio.get_event_loop().run_until_complete(executor.execute(task, repo))
    assert result["completed"] == 1
    assert result["failed"] == 1  # email
    # s2 should still complete
    assert task.steps[1].state == StepState.COMPLETED

def test_concurrency_limit_respected():
    """Max parallel steps capped at policy limit."""
    concurrent = [0]
    max_seen = [0]

    async def track_concurrency(tool, params):
        concurrent[0] += 1
        max_seen[0] = max(max_seen[0], concurrent[0])
        await asyncio.sleep(0.05)
        concurrent[0] -= 1
        return ActionResult.ok("ok")

    executor = DAGExecutor(step_runner=track_concurrency, max_parallel=2)
    task = Task(title="Concurrency test")
    task.steps = [
        TaskStep(task_id=task.id, name=f"s{i}", action=f"tool_{i}")
        for i in range(6)
    ]
    repo = AsyncMock(spec=TaskRepository)
    repo.save_checkpoint = AsyncMock()
    repo.append_event = AsyncMock()
    repo.update_task = AsyncMock()

    asyncio.get_event_loop().run_until_complete(executor.execute(task, repo))
    assert max_seen[0] <= 2
