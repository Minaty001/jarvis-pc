"""JARVIS Action Registry and standard actions."""

from __future__ import annotations

from typing import Dict, List, Optional
from .base import ActionResult, BaseAction
from .app_actions import CloseAppAction, OpenAppAction
from .hardware_actions import BrightnessAction, WifiStatusAction
from .media_actions import MediaNextAction, MediaPlayPauseAction, MediaPreviousAction
from .system_actions import LockScreenAction, ScreenshotAction, SystemStatsAction, VolumeAction
from .utility_actions import DateAction, NotifyAction, TimeAction
from .web_actions import OpenUrlAction, WebSearchAction
from .window_actions import FocusWindowAction, RestoreWindowsAction, ShowDesktopAction


class ActionRegistry:
    """Central registry holding all available JARVIS actions."""

    def __init__(self) -> None:
        self._actions: Dict[str, BaseAction] = {}
        self._register_default_actions()

    def register(self, action: BaseAction) -> None:
        """Register a new action."""
        self._actions[action.name] = action

    def get(self, name: str) -> Optional[BaseAction]:
        """Get an action by name."""
        return self._actions.get(name)

    def all_actions(self) -> List[BaseAction]:
        """Return list of all registered actions."""
        return list(self._actions.values())

    def _register_default_actions(self) -> None:
        """Register built-in system, app, media, hardware, web, and utility actions."""
        defaults = [
            VolumeAction(),
            SystemStatsAction(),
            ScreenshotAction(),
            LockScreenAction(),
            OpenAppAction(),
            CloseAppAction(),
            WebSearchAction(),
            OpenUrlAction(),
            TimeAction(),
            DateAction(),
            NotifyAction(),
            # New Desktop Superpowers
            MediaPlayPauseAction(),
            MediaNextAction(),
            MediaPreviousAction(),
            BrightnessAction(),
            WifiStatusAction(),
            ShowDesktopAction(),
            RestoreWindowsAction(),
            FocusWindowAction(),
        ]
        for action in defaults:
            self.register(action)


__all__ = [
    "ActionRegistry",
    "ActionResult",
    "BaseAction",
    "VolumeAction",
    "SystemStatsAction",
    "ScreenshotAction",
    "LockScreenAction",
    "OpenAppAction",
    "CloseAppAction",
    "WebSearchAction",
    "OpenUrlAction",
    "TimeAction",
    "DateAction",
    "NotifyAction",
    "MediaPlayPauseAction",
    "MediaNextAction",
    "MediaPreviousAction",
    "BrightnessAction",
    "WifiStatusAction",
    "ShowDesktopAction",
    "RestoreWindowsAction",
    "FocusWindowAction",
]
