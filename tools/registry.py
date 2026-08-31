"""
Tool Registry — Central registry of all available tools with metadata.
Maps tool names to implementations and tracks usage.
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class ToolCategory(Enum):
    SYSTEM = "system"
    FILE = "file"
    NETWORK = "network"
    APPLICATION = "application"
    MEMORY = "memory"
    VOICE = "voice"
    COMPUTER = "computer"
    CUSTOM = "custom"


class RiskLevel(Enum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ToolDef:
    """Definition of a registered tool."""
    name: str
    description: str
    category: ToolCategory
    risk_level: RiskLevel
    handler: Callable
    requires_confirmation: bool = False
    requires_permission: bool = False
    cooldown_seconds: float = 0.0
    max_calls_per_minute: float = 0.0
    parameters: dict = field(default_factory=dict)
    examples: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    enabled: bool = True


class ToolRegistry:
    """Central registry of all tools with metadata and access control."""

    def __init__(self):
        self._tools: dict[str, ToolDef] = {}
        self._call_log: list[dict] = []
        self._call_counts: dict[str, list[float]] = {}

    def register(self, tool: ToolDef) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> bool:
        if name in self._tools:
            del self._tools[name]
            return True
        return False

    def get(self, name: str) -> Optional[ToolDef]:
        return self._tools.get(name)

    def list_tools(self, category: Optional[ToolCategory] = None) -> list[ToolDef]:
        tools = list(self._tools.values())
        if category:
            tools = [t for t in tools if t.category == category]
        return [t for t in tools if t.enabled]

    def search(self, query: str) -> list[ToolDef]:
        query_lower = query.lower()
        results = []
        for tool in self._tools.values():
            score = 0
            if query_lower in tool.name.lower():
                score += 2
            if query_lower in tool.description.lower():
                score += 1
            if any(query_lower in tag.lower() for tag in tool.tags):
                score += 1
            if score > 0:
                results.append((score, tool))
        results.sort(key=lambda x: x[0], reverse=True)
        return [t for _, t in results]

    def can_call(self, name: str) -> tuple[bool, str]:
        """Check if a tool can be called right now (rate limiting)."""
        tool = self._tools.get(name)
        if not tool:
            return False, f"Tool '{name}' not found"
        if not tool.enabled:
            return False, f"Tool '{name}' is disabled"

        # Rate limiting
        if tool.max_calls_per_minute > 0:
            now = time.time()
            calls = self._call_counts.get(name, [])
            calls = [t for t in calls if now - t < 60]
            if len(calls) >= tool.max_calls_per_minute:
                return False, f"Rate limit exceeded for '{name}' ({tool.max_calls_per_minute}/min)"

        return True, ""

    def record_call(self, name: str, success: bool, duration: float) -> None:
        """Record a tool call for rate limiting and analytics."""
        now = time.time()
        self._call_counts.setdefault(name, []).append(now)
        self._call_log.append({
            "tool": name,
            "success": success,
            "duration": duration,
            "timestamp": now,
        })
        # Keep last 1000 calls
        if len(self._call_log) > 1000:
            self._call_log = self._call_log[-1000:]

    def get_call_stats(self) -> dict:
        """Get tool usage statistics."""
        stats = {}
        for entry in self._call_log:
            name = entry["tool"]
            if name not in stats:
                stats[name] = {"calls": 0, "successes": 0, "total_duration": 0}
            stats[name]["calls"] += 1
            if entry["success"]:
                stats[name]["successes"] += 1
            stats[name]["total_duration"] += entry["duration"]
        return stats


tool_registry = ToolRegistry()


def _register_defaults(registry: ToolRegistry):
    try:
        from tools.builtin import app_control, media_control, shell_exec, web_search
        _builtin_tools = [
            ToolDef(name="open_app", description="Open an application by name",
                    category=ToolCategory.APPLICATION, risk_level=RiskLevel.LOW,
                    handler=app_control.open_app,
                    parameters={"app_name": {"type": "string", "required": True}}),
            ToolDef(name="close_app", description="Close an application",
                    category=ToolCategory.APPLICATION, risk_level=RiskLevel.LOW,
                    handler=app_control.close_app,
                    parameters={"app_name": {"type": "string", "required": True}}),
            ToolDef(name="media_play", description="Play media or search music",
                    category=ToolCategory.COMPUTER, risk_level=RiskLevel.LOW,
                    handler=media_control.media_play,
                    parameters={"query": {"type": "string", "required": False}}),
            ToolDef(name="media_pause", description="Pause media playback",
                    category=ToolCategory.COMPUTER, risk_level=RiskLevel.LOW,
                    handler=media_control.media_pause),
            ToolDef(name="set_volume", description="Set system volume level",
                    category=ToolCategory.COMPUTER, risk_level=RiskLevel.LOW,
                    handler=media_control.set_volume,
                    parameters={"level": {"type": "string", "required": True}}),
            ToolDef(name="play_on_youtube",
                    description="Search and play a song or video on YouTube in the browser",
                    category=ToolCategory.NETWORK, risk_level=RiskLevel.LOW,
                    handler=media_control.play_on_youtube,
                    parameters={"query": {"type": "string", "required": True}}),
            ToolDef(name="play_on_spotify",
                    description="Search and play a song on Spotify",
                    category=ToolCategory.NETWORK, risk_level=RiskLevel.LOW,
                    handler=media_control.play_on_spotify,
                    parameters={"query": {"type": "string", "required": True}}),
            ToolDef(name="run_command", description="Execute a shell command",
                    category=ToolCategory.SYSTEM, risk_level=RiskLevel.HIGH,
                    handler=shell_exec.run_command, requires_confirmation=True,
                    parameters={"command": {"type": "string", "required": True}}),
            ToolDef(name="web_search", description="Search the web",
                    category=ToolCategory.NETWORK, risk_level=RiskLevel.LOW,
                    handler=web_search.web_search,
                    parameters={"query": {"type": "string", "required": True}}),
        ]
        for t in _builtin_tools:
            registry.register(t)
    except Exception:
        pass


_register_defaults(tool_registry)
