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


def test_cli_run_subcommand(capsys):
    from unittest.mock import AsyncMock
    from jarvis.app.application import Application
    mock_app = AsyncMock(spec=Application)
    run_cli(["run"], app=mock_app)
    captured = capsys.readouterr()
    assert "Starting JARVIS" in captured.out
    mock_app.run_until_stopped.assert_called_once()
