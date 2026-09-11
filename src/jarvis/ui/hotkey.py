"""
Global X11 desktop hotkey manager for Linux Mint / Cinnamon using Keybinder 3.0.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)

KEYBINDER_AVAILABLE = False
Keybinder = None
try:
    import gi
    gi.require_version("Keybinder", "3.0")
    from gi.repository import GLib, Keybinder
    KEYBINDER_AVAILABLE = True
except (ImportError, ValueError, AttributeError) as exc:
    logger.debug("Keybinder 3.0 not available: %s", exc)


class GlobalHotkeyManager:
    """Manages system-wide global keybindings in Linux Mint / Cinnamon."""

    def __init__(self) -> None:
        self._bound_keys: set[str] = set()
        self._initialized = False
        if KEYBINDER_AVAILABLE and Keybinder:
            try:
                Keybinder.init()
                self._initialized = True
            except Exception as exc:
                logger.warning("Failed to initialize Keybinder: %s", exc)

    @property
    def available(self) -> bool:
        return self._initialized

    def bind(self, keystring: str, callback: Callable[[], None]) -> bool:
        """Bind a global hotkey (e.g. '<Super>Space' or '<Ctrl><Alt>j')."""
        if not self._initialized or not Keybinder:
            logger.debug("Cannot bind '%s': Keybinder not initialized.", keystring)
            return False

        def _on_keypress(_keystring: str, _user_data: None) -> None:
            logger.info("Global hotkey triggered: %s", keystring)
            try:
                GLib.idle_add(callback)
            except Exception as exc:
                logger.error("Error invoking hotkey callback: %s", exc)

        try:
            ok = Keybinder.bind(keystring, _on_keypress, None)
            if ok:
                self._bound_keys.add(keystring)
                logger.info("Successfully bound global hotkey '%s'.", keystring)
                return True
            logger.warning("Failed to bind global hotkey '%s'.", keystring)
            return False
        except Exception as exc:
            logger.warning("Exception binding hotkey '%s': %s", keystring, exc)
            return False

    def unbind(self, keystring: Optional[str] = None) -> None:
        """Unbind a specific hotkey or all registered hotkeys."""
        if not self._initialized or not Keybinder:
            return

        to_remove = [keystring] if keystring else list(self._bound_keys)
        for key in to_remove:
            try:
                Keybinder.unbind(key)
                self._bound_keys.discard(key)
                logger.debug("Unbound global hotkey '%s'.", key)
            except Exception as exc:
                logger.warning("Error unbinding '%s': %s", key, exc)
