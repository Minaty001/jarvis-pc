# tests/task_engine/test_integration.py
import asyncio, pytest
from unittest.mock import AsyncMock, patch

def test_orchestrator_uses_task_manager():
    """CognitiveOrchestrator.process_goal routes through TaskManager."""
    from cognitive.orchestrator import cognitive_orchestrator
    with patch("task_engine.manager.task_manager.submit") as mock_submit:
        mock_task = AsyncMock()
        mock_task.id = "task-test"
        mock_task.state.value = "COMPLETED"
        mock_task.completed_steps.return_value = []
        mock_task.failed_steps.return_value = []
        mock_task.steps = []
        mock_task.progress.return_value = 1.0
        mock_task.error = ""
        mock_submit.return_value = mock_task

        result = asyncio.get_event_loop().run_until_complete(
            cognitive_orchestrator.process_goal("play pi loon song on youtube")
        )
        assert "status" in result

def test_multi_action_splits_into_steps():
    """Compound goals become multiple TaskSteps."""
    from task_engine.manager import TaskManager
    mgr = TaskManager()
    mgr._repo = AsyncMock()
    mgr._repo.create_task = AsyncMock()
    mgr._repo.append_event = AsyncMock()

    from task_engine.models import Task
    task = Task(title="test")
    steps = asyncio.get_event_loop().run_until_complete(
        mgr._build_steps(task, "play pi loon song or uske baad github trending dikhao")
    )
    assert len(steps) == 2
    assert steps[0].action in ("media_play", "play_on_youtube")
    assert steps[1].dependencies == [steps[0].id]
