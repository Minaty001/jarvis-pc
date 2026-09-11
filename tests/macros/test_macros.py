"""Unit tests for Voice-Activated Workflow Macros & Action Chaining."""

from unittest.mock import MagicMock, patch
import pytest

from jarvis.macros.engine import MacroEngine, MacroExecutionResult
from jarvis.macros.models import MacroDefinition, MacroStep, StepType
from jarvis.macros.store import MacroStore
from jarvis.tools.builtin.macro_tools import (
    create_macro,
    delete_macro,
    list_macros,
    run_macro,
    toggle_macro,
)
from jarvis.cli.main import run_cli


@pytest.fixture
def temp_macro_store(tmp_path):
    cfg_file = tmp_path / "macros.yaml"
    store = MacroStore(config_path=cfg_file)
    return store


def test_macro_store_defaults_and_crud(temp_macro_store):
    """Verify default preset macros are seeded and CRUD operations function properly."""
    store = temp_macro_store
    macros = store.list_macros()
    assert len(macros) >= 4

    names = [m.name for m in macros]
    assert "coding_mode" in names
    assert "meeting_prep" in names
    assert "system_health_check" in names
    assert "lockdown" in names

    # Create new macro
    custom = MacroDefinition(
        name="custom_backup",
        description="Backup project files",
        triggers=["backup project", "create backup"],
        steps=[MacroStep(type=StepType.SPEAK, target="Backup complete.")],
    )
    store.save_macro(custom)
    assert store.get_macro("custom_backup") is not None

    # Delete macro
    assert store.delete_macro("custom_backup")
    assert store.get_macro("custom_backup") is None


def test_macro_trigger_matching(temp_macro_store):
    """Test natural language trigger matching for voice commands."""
    engine = MacroEngine(store=temp_macro_store)

    # 1. Exact trigger
    m1 = engine.find_macro_by_trigger("enter coding mode")
    assert m1 is not None
    assert m1.name == "coding_mode"

    # 2. Voice command with filler words
    m2 = engine.find_macro_by_trigger("hey jarvis please prepare for meeting now")
    assert m2 is not None
    assert m2.name == "meeting_prep"

    # 3. Unmatched command
    m3 = engine.find_macro_by_trigger("what is the weather today")
    assert m3 is None


def test_macro_pipeline_execution(temp_macro_store):
    """Test sequential execution of multi-step pipeline."""
    engine = MacroEngine(store=temp_macro_store)

    pipeline = MacroDefinition(
        name="test_pipeline",
        steps=[
            MacroStep(type=StepType.SPEAK, target="Pipeline started."),
            MacroStep(type=StepType.COMMAND, target="echo 'JARVIS_OK'"),
            MacroStep(type=StepType.NOTIFY, target="JARVIS Test", args={"message": "All steps ok."}),
            MacroStep(type=StepType.PAUSE, target="0.01"),
        ],
    )

    with patch("jarvis.macros.engine.speak") as mock_speak, \
         patch("jarvis.macros.engine.notify", return_value=True) as mock_notify:

        res = engine.execute_macro(pipeline)
        assert res.success
        assert res.steps_completed == 4
        assert res.total_steps == 4
        assert mock_speak.called
        assert mock_notify.called
        assert "JARVIS_OK" in res.outputs[1]["output"]


def test_macro_step_failure_and_abort(temp_macro_store):
    """Verify macro aborts on error when ignore_errors is False."""
    engine = MacroEngine(store=temp_macro_store)

    failing_pipeline = MacroDefinition(
        name="failing_pipeline",
        steps=[
            MacroStep(type=StepType.COMMAND, target="false", ignore_errors=False),
            MacroStep(type=StepType.SPEAK, target="Should not be reached."),
        ],
    )

    with patch("jarvis.macros.engine.speak") as mock_speak:
        res = engine.execute_macro(failing_pipeline)
        assert not res.success
        assert res.steps_completed == 0
        assert not mock_speak.called


def test_macro_builtin_tools(temp_macro_store, monkeypatch):
    """Test builtin tools: list_macros, run_macro, create_macro, toggle_macro, delete_macro."""
    from jarvis.tools.builtin import macro_tools

    engine = MacroEngine(store=temp_macro_store)
    monkeypatch.setattr(macro_tools, "_GLOBAL_ENGINE", engine)

    # 1. List
    list_str = list_macros()
    assert "coding_mode" in list_str
    assert "meeting_prep" in list_str

    # 2. Create
    create_res = create_macro(
        name="night_mode",
        triggers=["good night", "night mode"],
        steps=[{"type": "speak", "target": "Good night, sir."}],
        description="Evening shutdown macro",
    )
    assert "night_mode" in create_res

    # 3. Toggle
    toggle_res = toggle_macro("night_mode", False)
    assert "DISABLED" in toggle_res

    # 4. Run
    with patch("jarvis.macros.engine.speak"):
        run_res = run_macro("coding_mode")
        assert "executed successfully" in run_res

    # 5. Delete
    del_res = delete_macro("night_mode")
    assert "deleted" in del_res


def test_cli_macro_subcommands(capsys):
    """Test CLI commands: jarvis macro list and jarvis macro show."""
    # 1. List
    ret = run_cli(["macro", "list"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "JARVIS Automated Workflow Macros" in out
    assert "coding_mode" in out

    # 2. Show
    ret = run_cli(["macro", "show", "coding_mode"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "Workflow Macro: coding_mode" in out
    assert "Pipeline Steps:" in out
