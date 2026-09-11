import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from jarvis.cli.main import run_cli
from jarvis.app.application import Application


def test_run_cli_help(capsys):
    run_cli(["help"])
    captured = capsys.readouterr()
    assert "usage: jarvis" in captured.out.lower() or "jarvis" in captured.out.lower()


def test_run_cli_launches_application(monkeypatch, capsys):
    mock_app = AsyncMock()
    mock_agent = AsyncMock()
    mock_agent.respond.return_value = "At your command, sir."
    mock_app.agent = mock_agent
    mock_app.settings = SimpleNamespace(confirmation_secret=None)

    # Empty stdin: the REPL sees EOF and shuts down cleanly.
    def raise_eof(_prompt=""):
        raise EOFError

    monkeypatch.setattr("builtins.input", raise_eof)

    ret = run_cli(["run"], app=mock_app)
    assert ret == 0
    captured = capsys.readouterr()
    assert "JARVIS at your service" in captured.out
    assert "Shutting down." in captured.out
