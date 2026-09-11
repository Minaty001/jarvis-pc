"""Unit tests for desktop notification subsystem."""

from unittest.mock import MagicMock
from jarvis.system.notifications import notify, _get_icon_path


def test_get_icon_path_returns_string():
    icon = _get_icon_path()
    assert isinstance(icon, str)
    assert len(icon) > 0


def test_notify_subprocess_fallback(monkeypatch):
    mock_run = MagicMock()
    monkeypatch.setattr("subprocess.run", mock_run)
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/notify-send" if name == "notify-send" else None)

    # Force GObject import to fail in this test
    monkeypatch.setattr("gi.require_version", MagicMock(side_effect=ImportError))

    res = notify("Test Title", "Test Message", urgency="critical")
    assert res is True
    assert mock_run.called
    args = mock_run.call_args[0][0]
    assert args[0] == "/usr/bin/notify-send"
    assert "critical" in args
    assert "Test Title" in args
    assert "Test Message" in args
