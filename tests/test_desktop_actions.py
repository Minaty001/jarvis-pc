from unittest.mock import MagicMock, patch
import pytest

from jarvis.actions import (
    ActionRegistry,
    BrightnessAction,
    FocusWindowAction,
    MediaNextAction,
    MediaPlayPauseAction,
    MediaPreviousAction,
    RestoreWindowsAction,
    ShowDesktopAction,
    WifiStatusAction,
)
from jarvis.planner import TaskPlanner


def test_registry_contains_new_actions():
    reg = ActionRegistry()
    assert reg.get("media_play_pause") is not None
    assert reg.get("media_next") is not None
    assert reg.get("media_previous") is not None
    assert reg.get("set_brightness") is not None
    assert reg.get("wifi_status") is not None
    assert reg.get("show_desktop") is not None
    assert reg.get("restore_windows") is not None
    assert reg.get("focus_window") is not None


def test_media_actions_mocked():
    with patch("jarvis.actions.media_actions.send_mpris_command", return_value=True):
        res1 = MediaPlayPauseAction().execute()
        assert res1.success is True
        assert "toggled" in res1.message

        res2 = MediaNextAction().execute()
        assert res2.success is True
        assert "next" in res2.message

        res3 = MediaPreviousAction().execute()
        assert res3.success is True
        assert "previous" in res3.message


def test_brightness_action_execution():
    with patch("jarvis.actions.hardware_actions.get_primary_display", return_value="eDP-1"), \
         patch("subprocess.run") as mock_run:
        action = BrightnessAction()
        res = action.execute(level=75)
        assert res.success is True
        assert "75 percent" in res.message
        assert mock_run.called
        args = mock_run.call_args[0][0]
        assert "eDP-1" in args
        assert "0.75" in args


def test_wifi_status_action():
    mock_out = "yes:Office-5G\nno:Guest-WiFi\n"
    with patch("shutil.which", return_value="/usr/bin/nmcli"), \
         patch("subprocess.check_output", return_value=mock_out):
        action = WifiStatusAction()
        res = action.execute()
        assert res.success is True
        assert "Office-5G" in res.message


def test_window_actions():
    with patch("shutil.which", return_value="/usr/bin/wmctrl"), \
         patch("subprocess.run") as mock_run:
        res1 = ShowDesktopAction().execute()
        assert res1.success is True
        assert "Desktop shown" in res1.message

        res2 = RestoreWindowsAction().execute()
        assert res2.success is True
        assert "Windows restored" in res2.message

        res3 = FocusWindowAction().execute(app_name="chrome")
        assert res3.success is True
        assert "chrome" in res3.message


def test_planner_multi_action_with_desktop_superpowers():
    planner = TaskPlanner()
    command = "show desktop, pause music, and set brightness to 80%"
    steps = planner.plan(command)

    assert len(steps) == 3
    assert steps[0].action.name == "show_desktop"
    assert steps[1].action.name == "media_play_pause"
    assert steps[2].action.name == "set_brightness"
    assert steps[2].params.get("level") == "80"
