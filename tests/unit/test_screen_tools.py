"""
Unit tests for screen capture and window inspection tools.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis.system.process import ProcessResult
from jarvis.tools.builtin.screen import (
    _resolve_output_path,
    get_active_window,
    list_open_windows,
    take_screenshot,
)


def test_resolve_output_path_in_home(tmp_path: Path):
    target = tmp_path / "custom.png"
    with patch("pathlib.Path.home", return_value=tmp_path):
        resolved = _resolve_output_path(str(target))
    assert resolved == target.resolve()


def test_resolve_output_path_outside_home(tmp_path: Path):
    with patch("pathlib.Path.home", return_value=tmp_path):
        with pytest.raises(ValueError, match="must be saved within your home directory"):
            _resolve_output_path("/etc/forbidden.png")


@pytest.mark.asyncio
async def test_take_screenshot_gdk_success(tmp_path: Path):
    target = tmp_path / "screen.png"

    mock_pixbuf = MagicMock()

    def mock_savev(path, fmt, keys, vals):
        target.write_bytes(b"\x89PNG\r\n\x1a\ntest_png_data")

    mock_pixbuf.savev.side_effect = mock_savev

    mock_root = MagicMock()
    mock_root.get_width.return_value = 1920
    mock_root.get_height.return_value = 1080

    mock_gdk = MagicMock()
    mock_gdk.get_default_root_window.return_value = mock_root
    mock_gdk.pixbuf_get_from_window.return_value = mock_pixbuf

    with patch("pathlib.Path.home", return_value=tmp_path), \
         patch("jarvis.tools.builtin.screen.GDK_AVAILABLE", True), \
         patch("jarvis.tools.builtin.screen.Gdk", mock_gdk):
        res = await take_screenshot(output_path=str(target))

    assert "Screenshot captured successfully" in res
    assert str(target) in res


@pytest.mark.asyncio
async def test_get_active_window_success():
    root_xprop = ProcessResult(
        returncode=0,
        stdout="_NET_ACTIVE_WINDOW(WINDOW): window id # 0x4000006\n",
        stderr="",
    )
    detail_xprop = ProcessResult(
        returncode=0,
        stdout='WM_NAME(STRING) = "jarvis-pc - Visual Studio Code"\nWM_CLASS(STRING) = "code", "Code"\n',
        stderr="",
    )

    async def mock_run_process(cmd, timeout=5.0):
        if "-root" in cmd:
            return root_xprop
        return detail_xprop

    with patch("shutil.which", return_value="/usr/bin/xprop"), \
         patch("jarvis.tools.builtin.screen.run_process", side_effect=mock_run_process):
        info = await get_active_window()

    assert info["window_id"] == "0x4000006"
    assert "Visual Studio Code" in info["title"]
    assert "code" in info["app_class"]


@pytest.mark.asyncio
async def test_list_open_windows_success():
    wmctrl_out = ProcessResult(
        returncode=0,
        stdout="0x04000006  0 code.Code  hostname VS Code\n0x02e00003  0 nemo.Nemo  hostname Files\n",
        stderr="",
    )

    with patch("shutil.which", return_value="/usr/bin/wmctrl"), \
         patch("jarvis.tools.builtin.screen.run_process", return_value=wmctrl_out):
        windows = await list_open_windows()

    assert len(windows) == 2
    assert windows[0]["window_id"] == "0x04000006"
    assert windows[0]["app_class"] == "code.Code"
    assert windows[1]["app_class"] == "nemo.Nemo"
