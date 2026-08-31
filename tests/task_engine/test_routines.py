# tests/task_engine/test_routines.py
import asyncio, pytest
from unittest.mock import AsyncMock
from task_engine.routines import RoutineManager
from task_engine.models import TaskTemplate

def test_builtin_templates_exist():
    mgr = RoutineManager()
    templates = mgr.list_templates()
    names = [t["name"] for t in templates]
    assert "morning_briefing" in names
    assert "work_start" in names
    assert "evening_routine" in names

def test_register_custom_template():
    mgr = RoutineManager()
    tmpl = TaskTemplate(
        name="workout",
        description="Daily workout reminder",
        step_blueprints=[{"action": "send_notification", "parameters": {"message": "Time to work out!"}}],
        tags=["health"],
    )
    mgr.register_template(tmpl)
    names = [t["name"] for t in mgr.list_templates()]
    assert "workout" in names

def test_create_routine_submits_task():
    mgr = RoutineManager()
    mock_manager = AsyncMock()
    mock_task = AsyncMock()
    mock_task.id = "task-r1"
    mock_manager.submit = AsyncMock(return_value=mock_task)
    mgr.inject_task_manager(mock_manager)

    task = asyncio.get_event_loop().run_until_complete(
        mgr.create_routine("morning_briefing", "every weekday at 8 AM")
    )
    assert task.id == "task-r1"
    mock_manager.submit.assert_called_once()
