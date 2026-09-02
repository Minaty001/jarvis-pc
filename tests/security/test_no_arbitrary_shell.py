from pathlib import Path


def test_shell_exec_file_does_not_exist():
    """The arbitrary shell execution tool file must not exist."""
    assert not Path("tools/builtin/shell_exec.py").exists()


def test_no_run_command_in_registry():
    """No tool named 'run_command' or 'shell_exec' may exist in the canonical registry."""
    from jarvis.app.application import Application

    app = Application()
    assert not app.registry.has("run_command")
    assert not app.registry.has("shell_exec")
