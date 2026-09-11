from jarvis.cli.doctor import run_doctor
from jarvis.cli.main import run_cli


def test_cli_doctor_output():
    report = run_doctor()
    assert "JARVIS Linux Doctor" in report
    assert "OS:" in report


def test_cli_version_subcommand(capsys):
    run_cli(["version"])
    captured = capsys.readouterr()
    assert "v1.0.0" in captured.out


def test_cli_status_subcommand(capsys):
    run_cli(["status"])
    captured = capsys.readouterr()
    assert "Status" in captured.out


def test_cli_run_subcommand(monkeypatch, capsys):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    mock_app = AsyncMock()
    mock_agent = AsyncMock()
    mock_agent.respond.return_value = "At your command, sir."
    mock_app.agent = mock_agent
    mock_app.settings = SimpleNamespace(confirmation_secret=None)

    script = ["hello", "exit"]
    monkeypatch.setattr("builtins.input", lambda prompt: script.pop(0))

    run_cli(["run"], app=mock_app)
    captured = capsys.readouterr()
    assert "Starting JARVIS" in captured.out
    assert "At your command, sir." in captured.out
    mock_agent.respond.assert_called_once_with("hello", session_id="cli")
