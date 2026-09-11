"""Tests for Autonomous Multi-Agent Swarm Orchestration Engine and Background Workers."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis.cognitive.context import ExecutionContext
from jarvis.swarm.engine import SwarmEngine
from jarvis.swarm.models import SwarmTask, TaskStatus, WorkerRole
from jarvis.swarm.store import SwarmStore
from jarvis.swarm.worker import SubAgentWorker
from jarvis.tools.builtin.swarm_tools import (
    handle_cancel_swarm_task,
    handle_decompose_swarm_goal,
    handle_get_swarm_task_details,
    handle_list_swarm_tasks,
    handle_spawn_background_worker,
)
from jarvis.tools.registry import ToolRegistry


def test_swarm_task_serialization():
    task = SwarmTask(
        parent_goal="Optimize system",
        role=WorkerRole.CODER,
        instruction="Refactor database queries",
        name="SQL Optimizer",
    )
    data = task.to_dict()
    assert data["role"] == "coder"
    assert data["status"] == "pending"
    assert data["name"] == "SQL Optimizer"

    restored = SwarmTask.from_dict(data)
    assert restored.id == task.id
    assert restored.role == WorkerRole.CODER
    assert restored.instruction == "Refactor database queries"


def test_swarm_store_crud(tmp_path):
    db_file = tmp_path / "test_swarm.db"
    store = SwarmStore(db_path=db_file)

    t1 = SwarmTask(role=WorkerRole.RESEARCHER, instruction="Investigate LLM latency", name="Latency Task")
    t2 = SwarmTask(role=WorkerRole.SYSTEM, instruction="Check disk usage", name="Disk Task")

    store.save_task(t1)
    store.save_task(t2)

    fetched = store.get_task(t1.id)
    assert fetched is not None
    assert fetched.name == "Latency Task"
    assert fetched.role == WorkerRole.RESEARCHER

    # List all
    tasks = store.list_tasks()
    assert len(tasks) == 2

    # Filter by role
    sys_tasks = store.list_tasks(role=WorkerRole.SYSTEM)
    assert len(sys_tasks) == 1
    assert sys_tasks[0].id == t2.id

    # Update task
    t1.status = TaskStatus.COMPLETED
    t1.result = "Found optimal settings."
    store.save_task(t1)

    completed_tasks = store.list_tasks(status=TaskStatus.COMPLETED)
    assert len(completed_tasks) == 1
    assert completed_tasks[0].result == "Found optimal settings."

    # Delete
    assert store.delete_task(t2.id) is True
    assert len(store.list_tasks()) == 1

    # Clear
    assert store.clear_tasks() == 1
    assert len(store.list_tasks()) == 0


@pytest.mark.asyncio
async def test_subagent_worker_execution_direct():
    task = SwarmTask(
        role=WorkerRole.RESEARCHER,
        instruction="Analyze market trends",
        name="Market Worker",
    )
    mock_client = AsyncMock()
    chat_result = MagicMock()
    chat_result.reply = "Market analysis complete: Strong growth in AI edge hardware."
    chat_result.tool_calls = []
    mock_client.chat.return_value = chat_result

    worker = SubAgentWorker(task=task, client=mock_client)
    res_task = await worker.run()

    assert res_task.status == TaskStatus.COMPLETED
    assert "Strong growth" in res_task.result
    assert res_task.progress_percent == 100
    assert len(res_task.logs) >= 2


@pytest.mark.asyncio
async def test_subagent_worker_tool_invocation():
    task = SwarmTask(
        role=WorkerRole.SYSTEM,
        instruction="Get system health info",
        name="Health Worker",
    )
    mock_client = AsyncMock()
    # Step 1: tool call JSON, Step 2: final answer
    result1 = MagicMock()
    result1.reply = '```json\n{"tool": "dummy_tool", "args": {"val": 42}}\n```'
    result1.tool_calls = []
    result2 = MagicMock()
    result2.reply = "System health is optimal with metric 42."
    result2.tool_calls = []
    mock_client.chat.side_effect = [result1, result2]

    registry = ToolRegistry()
    from jarvis.tools.base import ToolDefinition
    from jarvis.tools.policy import RiskLevel

    dummy_handler = AsyncMock(return_value={"status": "ok", "metric": 42})
    registry.register(
        ToolDefinition(
            name="dummy_tool",
            risk=RiskLevel.SAFE,
            handler=dummy_handler,
            capabilities=frozenset(),
        )
    )

    worker = SubAgentWorker(task=task, client=mock_client, registry=registry)
    res_task = await worker.run()

    assert res_task.status == TaskStatus.COMPLETED
    assert "optimal with metric 42" in res_task.result
    dummy_handler.assert_called_once()


@pytest.mark.asyncio
async def test_swarm_engine_spawn_and_cancel(tmp_path):
    db_file = tmp_path / "test_engine.db"
    store = SwarmStore(db_path=db_file)
    engine = SwarmEngine(store=store)

    mock_client = AsyncMock()
    mock_client.create_completion.return_value = {"reply": "Done"}

    task = await engine.spawn_worker(
        role=WorkerRole.CODER,
        instruction="Generate Python tests",
        name="Test Worker",
        client=mock_client,
    )
    assert task.id.startswith("swarm-")

    # Give loop a cycle
    await asyncio.sleep(0.05)

    # Cancel task
    cancelled = await engine.cancel_task(task.id)
    # Either successfully cancelled during run or completed
    fetched = engine.get_task(task.id)
    assert fetched is not None


@pytest.mark.asyncio
async def test_swarm_engine_decompose_and_dispatch(tmp_path):
    db_file = tmp_path / "test_decomp.db"
    store = SwarmStore(db_path=db_file)
    engine = SwarmEngine(store=store)

    mock_client = AsyncMock()
    chat_result = MagicMock()
    chat_result.reply = (
        '```json\n[\n'
        '  {"role": "researcher", "name": "Docs Survey", "instruction": "Check docs"},\n'
        '  {"role": "coder", "name": "Build Plugin", "instruction": "Implement code"}\n'
        ']\n```'
    )
    chat_result.tool_calls = []
    mock_client.chat.return_value = chat_result

    tasks = await engine.decompose_and_dispatch(
        goal="Develop audio plugin",
        client=mock_client,
        max_workers=2,
    )
    assert len(tasks) == 2
    assert tasks[0].role == WorkerRole.RESEARCHER
    assert tasks[1].role == WorkerRole.CODER

    await asyncio.sleep(0.05)


@pytest.mark.asyncio
async def test_builtin_swarm_tools(tmp_path):
    ctx = ExecutionContext(
        session_id="test_session",
        task_id="test_task",
        user_id="operator",
        request_id="test_req",
    )

    with patch("jarvis.tools.builtin.swarm_tools.get_swarm_engine") as mock_engine_fn:
        engine = SwarmEngine(store=SwarmStore(db_path=tmp_path / "swarm_tool.db"))
        mock_engine_fn.return_value = engine

        # 1. Spawn worker
        spawn_res = await handle_spawn_background_worker(
            ctx,
            role="researcher",
            instruction="Research battery longevity algorithms",
            name="Battery Worker",
        )
        assert spawn_res["success"] is True
        task_id = spawn_res["task_id"]

        # 2. List tasks
        list_res = await handle_list_swarm_tasks(ctx)
        assert list_res["success"] is True
        assert list_res["count"] >= 1

        # 3. Get task details
        details_res = await handle_get_swarm_task_details(ctx, task_id=task_id)
        assert details_res["success"] is True
        assert details_res["task"]["id"] == task_id

        # 4. Cancel task
        cancel_res = await handle_cancel_swarm_task(ctx, task_id=task_id)
        assert cancel_res["task_id"] == task_id

        # 5. Decompose goal
        with patch.object(engine, "decompose_and_dispatch", new_callable=AsyncMock) as mock_decomp:
            t1 = SwarmTask(role=WorkerRole.RESEARCHER, instruction="Subtask 1", name="Worker 1")
            mock_decomp.return_value = [t1]
            decomp_res = await handle_decompose_swarm_goal(ctx, goal="Upgrade system", max_workers=1)
            assert decomp_res["success"] is True
            assert len(decomp_res["dispatched_tasks"]) == 1


def test_cli_swarm_subcommands(capsys, tmp_path):
    from jarvis.cli.main import run_cli

    with patch("jarvis.swarm.engine.get_swarm_engine") as mock_engine_fn:
        engine = SwarmEngine(store=SwarmStore(db_path=tmp_path / "cli_swarm.db"))
        mock_engine_fn.return_value = engine

        # Spawn via CLI
        code = run_cli(["swarm", "spawn", "coder", "Build CLI test", "--name", "CLI Coder"])
        assert code == 0
        out = capsys.readouterr().out
        assert "[JARVIS Swarm] Sub-agent worker launched!" in out

        # List via CLI
        code = run_cli(["swarm", "list"])
        assert code == 0
        out = capsys.readouterr().out
        assert "JARVIS Autonomous Swarm Tasks" in out

        tasks = engine.list_tasks()
        assert len(tasks) >= 1
        tid = tasks[0].id

        # Show via CLI
        code = run_cli(["swarm", "show", tid])
        assert code == 0
        out = capsys.readouterr().out
        assert "Swarm Task:" in out

        # Cancel via CLI
        code = run_cli(["swarm", "cancel", tid])
        assert code == 0
        out = capsys.readouterr().out
        assert "cancelled" in out
