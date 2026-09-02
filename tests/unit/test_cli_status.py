import subprocess
import pytest
from unittest.mock import MagicMock
from jarvis.cli.main import check_status


def test_status_reports_stopped_when_nothing_running(monkeypatch):
    """When systemctl and health both fail, status should be 'stopped'."""
    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **kw: MagicMock(stdout="inactive\n", returncode=3)
    )
    result = check_status()
    assert result == "stopped"


def test_status_does_not_hardcode_operational():
    """jarvis status must never hardcode 'operational'."""
    from pathlib import Path
    content = Path("src/jarvis/cli/main.py").read_text()
    assert "operational" not in content
