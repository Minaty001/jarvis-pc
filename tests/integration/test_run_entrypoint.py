import pytest
from unittest.mock import AsyncMock, patch
from jarvis.cli.main import run_cli
from jarvis.app.application import Application


def test_run_cli_help(capsys):
    run_cli(["help"])
    captured = capsys.readouterr()
    assert "usage: jarvis" in captured.out.lower() or "jarvis" in captured.out.lower()


def test_run_cli_launches_application():
    mock_app = AsyncMock(spec=Application)
    ret = run_cli(["run"], app=mock_app)
    assert ret == 0
    mock_app.run_until_stopped.assert_called_once()
