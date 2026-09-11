"""
Unit tests for Desktop Tray indicator and Global Hotkey manager.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from jarvis.ui.hotkey import GlobalHotkeyManager
from jarvis.ui.tray import JarvisTray


def test_hotkey_manager_mocked():
    mock_keybinder = MagicMock()
    mock_keybinder.bind.return_value = True

    with patch("jarvis.ui.hotkey.KEYBINDER_AVAILABLE", True), \
         patch("jarvis.ui.hotkey.Keybinder", mock_keybinder):
        mgr = GlobalHotkeyManager()
        assert mgr.available is True

        cb = MagicMock()
        ok = mgr.bind("<Super>space", cb)
        assert ok is True
        mock_keybinder.bind.assert_called_once()

        mgr.unbind("<Super>space")
        mock_keybinder.unbind.assert_called_with("<Super>space")


def test_hotkey_manager_unavailable():
    with patch("jarvis.ui.hotkey.KEYBINDER_AVAILABLE", False), \
         patch("jarvis.ui.hotkey.Keybinder", None):
        mgr = GlobalHotkeyManager()
        assert mgr.available is False
        assert mgr.bind("<Super>space", lambda: None) is False
        mgr.unbind()  # Should not raise


def test_tray_initialization():
    on_toggle_win = MagicMock()
    on_toggle_orb = MagicMock()
    on_quit = MagicMock()

    tray = JarvisTray(
        on_toggle_window=on_toggle_win,
        on_toggle_orb=on_toggle_orb,
        on_quit=on_quit,
    )
    # Destroy should run cleanly
    tray.destroy()
