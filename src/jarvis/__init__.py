"""JARVIS - Voice Assistant and Multi-Action Task Execution Engine"""

from .actions import (
    ActionRegistry,
    ActionResult,
    BaseAction,
    CloseAppAction,
    DateAction,
    LockScreenAction,
    NotifyAction,
    OpenAppAction,
    OpenUrlAction,
    ScreenshotAction,
    SystemStatsAction,
    TimeAction,
    VolumeAction,
    WebSearchAction,
)
from .audio_device import detect_and_configure_bluetooth_mic, get_active_microphone_name
from .brain import LLMBrain
from .config import LLMConfig, get_llm_config
from .engine import EngineState, JarvisEngine
from .planner import ExecutionReport, TaskPlanner, TaskStep
from .stt import StreamTranscriber
from .voice import init_voice, speak_text, speak_yes_boss, speak_yes_boss_async
from .wake_word import WakeWordDetector

__all__ = [
    "JarvisEngine",
    "EngineState",
    "WakeWordDetector",
    "TaskPlanner",
    "TaskStep",
    "ExecutionReport",
    "StreamTranscriber",
    "LLMBrain",
    "LLMConfig",
    "get_llm_config",
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
    "detect_and_configure_bluetooth_mic",
    "get_active_microphone_name",
    "init_voice",
    "speak_text",
    "speak_yes_boss",
    "speak_yes_boss_async",
]
