import pytest
from jarvis.planning.planner import TaskPlanner
from jarvis.tasks.models import TaskPlan
from jarvis.cognitive.orchestrator import Orchestrator
from jarvis.cognitive.context import ExecutionContext
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_planner_creates_task_plan():
    planner = TaskPlanner()
    plan = await planner.create_plan("Open Firefox")
    assert isinstance(plan, TaskPlan)
    assert len(plan.steps) > 0
    assert plan.steps[0].tool == "open_application"

@pytest.mark.asyncio
async def test_orchestrator_routes_to_task_manager():
    planner = TaskPlanner()
    mock_manager = MagicMock()
    mock_manager.execute_plan = AsyncMock(return_value={"step-1": "success"})

    orchestrator = Orchestrator(planner, mock_manager)
    ctx = ExecutionContext(
        session_id="s1",
        task_id="t1",
        user_id="u1",
        request_id="r1",
    )

    result = await orchestrator.process_request("Open Firefox", context=ctx)
    assert result == {"step-1": "success"}
    mock_manager.execute_plan.assert_called_once()
    call_args = mock_manager.execute_plan.call_args
    assert isinstance(call_args[0][0], TaskPlan)
    assert call_args[1]["context"] == ctx
