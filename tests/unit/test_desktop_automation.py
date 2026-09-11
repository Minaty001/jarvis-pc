"""Unit tests for X11 Desktop Automation and UI control tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from jarvis.tools.builtin.desktop_automation import (
    X11Controller,
    click_mouse,
    focus_window,
    locate_and_click,
    move_mouse,
    press_key,
    scroll_mouse,
    type_text,
)


@pytest.fixture
def mock_controller():
    controller = X11Controller()
    controller._available = True
    controller._display = 12345
    controller._x11 = MagicMock()
    controller._xtst = MagicMock()
    return controller


def test_x11_controller_mouse_actions(mock_controller):
    assert mock_controller.move_mouse(100, 200) is True
    assert mock_controller._xtst.XTestFakeMotionEvent.called

    assert mock_controller.click_mouse(x=150, y=250, button=1, clicks=2) is True
    assert mock_controller._xtst.XTestFakeButtonEvent.call_count == 4  # 2 press, 2 release


def test_x11_controller_key_actions(mock_controller):
    mock_controller._x11.XStringToKeysym.return_value = 0xFF0D  # Return
    mock_controller._x11.XKeysymToKeycode.return_value = 36     # Keycode

    assert mock_controller.type_string("Hi") is True
    assert mock_controller.key_combination(["ctrl", "c"]) is True


@pytest.mark.asyncio
async def test_async_click_mouse():
    with patch("jarvis.tools.builtin.desktop_automation._CONTROLLER") as mock_ctrl:
        mock_ctrl.is_available = True
        mock_ctrl.click_mouse.return_value = True

        msg = await click_mouse(300, 400, button="left")
        assert "Clicked left mouse button at (300, 400)" in msg


@pytest.mark.asyncio
async def test_async_move_and_scroll_mouse():
    with patch("jarvis.tools.builtin.desktop_automation._CONTROLLER") as mock_ctrl:
        mock_ctrl.is_available = True
        mock_ctrl.move_mouse.return_value = True

        msg = await move_mouse(500, 600)
        assert "Cursor moved to (500, 600)" in msg

        scroll_msg = await scroll_mouse(direction="down", amount=3)
        assert "Scrolled mouse down by 3 clicks" in scroll_msg


@pytest.mark.asyncio
async def test_async_type_and_press_key():
    with patch("jarvis.tools.builtin.desktop_automation._CONTROLLER") as mock_ctrl:
        mock_ctrl.is_available = True
        mock_ctrl.type_string.return_value = True
        mock_ctrl.key_combination.return_value = True

        type_msg = await type_text("Hello JARVIS")
        assert "Typed 12 characters" in type_msg

        key_msg = await press_key("Return")
        assert "Pressed key combination: 'Return'" in key_msg


@pytest.mark.asyncio
async def test_focus_window():
    with patch("jarvis.tools.builtin.desktop_automation.shutil.which", return_value="/usr/bin/wmctrl"), \
         patch("jarvis.tools.builtin.desktop_automation.run_process") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)

        res = await focus_window("Terminal")
        assert "Successfully focused window matching 'Terminal'" in res


@pytest.mark.asyncio
async def test_locate_and_click_success():
    with patch("jarvis.tools.builtin.desktop_automation.take_screenshot", new_callable=AsyncMock) as mock_snap, \
         patch("jarvis.tools.builtin.desktop_automation.analyze_image", new_callable=AsyncMock) as mock_vis, \
         patch("jarvis.tools.builtin.desktop_automation.click_mouse", new_callable=AsyncMock) as mock_click:

        mock_snap.return_value = "Screenshot captured successfully and saved to /tmp/screen.png (100 KB)."
        mock_vis.return_value = '{"found": true, "x": 640, "y": 480, "description": "save button"}'
        mock_click.return_value = "Clicked left mouse button at (640, 480) [clicks=1]."

        res = await locate_and_click("save button")
        assert "Visually located 'save button' at (640, 480)" in res
        mock_click.assert_awaited_once_with(x=640, y=480)
