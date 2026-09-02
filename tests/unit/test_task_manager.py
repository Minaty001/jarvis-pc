import pytest
from jarvis.tools.executor import ToolExecutor, ToolDefinition, RiskLevel
from jarvis.tasks.models import TaskPlan, TaskStep, StepStatus
from jarvis.tasks.manager import TaskManager


@pytest.mark.asyncio
async def test_task_manager_executes_plan_via_executor():
    executor = ToolExecutor()
    executed_args = []

    async def mock_handler(target: str):
        executed_args.append(target)
        return "success"

    executor.register(ToolDefinition("test_tool", RiskLevel.SAFE, mock_handler))
    manager = TaskManager(executor)

    plan = TaskPlan(
        id="plan-1",
        steps=[
            TaskStep(id="step-1", tool="test_tool", arguments={"target": "file.txt"})
        ]
    )

    from jarvis.cognitive.context import ExecutionContext
    ctx = ExecutionContext("s1", "t1", "u1", "r1")
    results = await manager.execute_plan(plan, context=ctx)
    assert results["step-1"] == "success"
    assert executed_args == ["file.txt"]
    assert plan.steps[0].status == StepStatus.COMPLETED


@pytest.mark.asyncio
async def test_task_manager_handles_step_failure():
    executor = ToolExecutor()

    async def failing_handler():
        raise ValueError("Something went wrong")

    executor.register(ToolDefinition("failing_tool", RiskLevel.SAFE, failing_handler))
    manager = TaskManager(executor)

    plan = TaskPlan(
        id="plan-fail",
        steps=[
            TaskStep(id="step-fail", tool="failing_tool")
        ]
    )

    from jarvis.cognitive.context import ExecutionContext
    ctx = ExecutionContext("s1", "t1", "u1", "r1")
    results = await manager.execute_plan(plan, context=ctx)
    assert "step-fail" not in results
    assert plan.steps[0].status == StepStatus.FAILED
    assert "Something went wrong" in plan.steps[0].error
