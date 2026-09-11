"""Unit tests for ReflectionEngine, Planner Priming, and CLI."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from jarvis.brain.reflection import ReflectionEngine
from jarvis.brain.goals import plan_goal
from jarvis.cli.main import run_cli


@pytest.mark.asyncio
async def test_reflection_engine_with_mock_llm():
    mock_client = AsyncMock()
    mock_client.chat.return_value = """
    {
        "category": "parameter_fix",
        "lesson": "Always specify camera_index as integer 0 rather than string '0'.",
        "recipe": ["check_camera()", "take_photo(camera_index=0)"]
    }
    """
    engine = ReflectionEngine(llm_client=mock_client)
    res = await engine.reflect_on_outcome(
        goal="take a photo",
        plan=["step 1"],
        transcript=["step 1 done"],
        verified=True,
    )
    assert res["category"] == "parameter_fix"
    assert "camera_index" in res["lesson"]
    assert res["recipe"] == ["check_camera()", "take_photo(camera_index=0)"]
    assert res["verified"] is True


@pytest.mark.asyncio
async def test_reflection_engine_heuristic_fallback():
    # When no client is provided, falls back cleanly
    engine = ReflectionEngine(llm_client=None)

    success_res = await engine.reflect_on_outcome(
        goal="check disk",
        plan=["step 1"],
        transcript=["step 1 done"],
        verified=True,
    )
    assert success_res["verified"] is True
    assert "Successful pattern" in success_res["lesson"]

    fail_res = await engine.reflect_on_outcome(
        goal="delete root",
        plan=["step 1"],
        transcript=["step 1 failed"],
        verified=False,
        error="Permission denied",
    )
    assert fail_res["verified"] is False
    assert "Failed pattern" in fail_res["lesson"]
    assert "Permission denied" in fail_res["lesson"]


@pytest.mark.asyncio
async def test_plan_goal_with_memory_priming():
    mock_client = AsyncMock()
    mock_result = MagicMock()
    mock_result.content = "1. First step\n2. Second step"
    mock_client.chat.return_value = mock_result

    mock_memory = MagicMock()
    mock_memory.recall_reflections.return_value = [
        {"lesson": "Do not execute sudo commands; check permissions first."}
    ]

    plan = await plan_goal(mock_client, "test goal", memory=mock_memory)
    assert plan == ["First step", "Second step"]

    # Verify that the past lesson was included in the planner prompt
    call_args = mock_client.chat.call_args[0][0]
    system_msg = call_args[0]["content"]
    assert "PAST LESSONS FOR SIMILAR GOALS" in system_msg
    assert "Do not execute sudo commands" in system_msg


def test_cli_reflections_subcommand(capsys):
    mock_app = MagicMock()
    mock_memory = MagicMock()
    mock_memory.list_reflections.return_value = [
        {
            "verified": True,
            "goal_query": "backup database",
            "category": "workflow_strategy",
            "lesson": "Dump SQLite via sqlite3 .dump command.",
            "recipe": ["step 1", "step 2"],
            "success_count": 3,
            "failure_count": 0,
        }
    ]
    mock_app.memory = mock_memory

    run_cli(["reflections"], app=mock_app)
    captured = capsys.readouterr()
    assert "JARVIS Metacognitive Reflections" in captured.out
    assert "backup database" in captured.out
    assert "workflow_strategy" in captured.out
    assert "Dump SQLite" in captured.out
