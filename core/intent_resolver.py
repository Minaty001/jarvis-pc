"""
Intent Resolver — Parse user text into structured intent.
Uses pattern matching for fast local resolution, LLM for complex cases.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from config.logger import get_logger

logger = get_logger("core.intent")


@dataclass
class Intent:
    action: str
    parameters: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    raw_text: str = ""


# Pattern-based intent mappings
PATTERNS = {
    # App control
    r"open\s+(.+)": lambda m: ("open_app", {"app_name": m.group(1).strip()}),
    r"launch\s+(.+)": lambda m: ("open_app", {"app_name": m.group(1).strip()}),
    r"start\s+(.+)": lambda m: ("open_app", {"app_name": m.group(1).strip()}),
    r"close\s+(.+)": lambda m: ("close_app", {"app_name": m.group(1).strip()}),
    r"quit\s+(.+)": lambda m: ("close_app", {"app_name": m.group(1).strip()}),
    r"kill\s+(.+)": lambda m: ("close_app", {"app_name": m.group(1).strip()}),

    # System info
    r"what time|current time|time is it": lambda m: ("get_time", {}),
    r"what date|current date|today.s date": lambda m: ("get_date", {}),
    r"battery|battery level|battery status": lambda m: ("get_battery", {}),
    r"cpu|cpu usage|processor": lambda m: ("get_cpu", {}),
    r"memory|ram|memory usage": lambda m: ("get_memory", {}),
    r"disk|storage|disk space": lambda m: ("get_disk", {}),
    r"network|internet|ip address": lambda m: ("get_network", {}),

    # File operations
    r"list files?\s*(?:in\s+)?(.+)?": lambda m: ("list_files", {"path": m.group(1) or "."}),
    r"create (?:a )?file\s+(.+)": lambda m: ("create_file", {"path": m.group(1).strip()}),
    r"delete (?:a )?file\s+(.+)": lambda m: ("delete_file", {"path": m.group(1).strip()}),

    # Web
    r"search\s+(?:for\s+)?(.+)": lambda m: ("web_search", {"query": m.group(1).strip()}),
    r"google\s+(.+)": lambda m: ("web_search", {"query": m.group(1).strip()}),

    # Screenshot
    r"screenshot|take (?:a )?screenshot|capture screen": lambda m: ("screenshot", {}),

    # Clipboard
    r"copy\s+(.+)": lambda m: ("clipboard_copy", {"text": m.group(1).strip()}),
    r"paste|what(?:'s| is) (?:on |in )?my clipboard": lambda m: ("clipboard_paste", {}),

    # Shell
    r"run\s+(.+)": lambda m: ("shell_exec", {"command": m.group(1).strip()}),
    r"execute\s+(.+)": lambda m: ("shell_exec", {"command": m.group(1).strip()}),

    # Git
    r"git status": lambda m: ("git_status", {}),
    r"git commit\s+(.+)": lambda m: ("git_commit", {"message": m.group(1).strip()}),
    r"git push": lambda m: ("git_push", {}),
    r"git pull": lambda m: ("git_pull", {}),

    # Docker
    r"docker (?:list )?containers?": lambda m: ("docker_ps", {}),
    r"docker images": lambda m: ("docker_images", {}),
    r"docker (?:start|run)\s+(.+)": lambda m: ("docker_start", {"container": m.group(1).strip()}),
    r"docker stop\s+(.+)": lambda m: ("docker_stop", {"container": m.group(1).strip()}),

    # Media
    r"play\s+(.+)": lambda m: ("media_play", {"query": m.group(1).strip()}),
    r"pause|stop (?:music|video|media)": lambda m: ("media_pause", {}),
    r"volume\s+(up|down|\d+)": lambda m: ("set_volume", {"level": m.group(1)}),
    r"mute": lambda m: ("set_volume", {"level": "0"}),
}


class IntentResolver:
    """Resolve user text to structured intent."""

    def resolve(self, text: str) -> Intent:
        text_lower = text.lower().strip()

        for pattern, handler in PATTERNS.items():
            match = re.search(pattern, text_lower)
            if match:
                action, params = handler(match)
                return Intent(
                    action=action,
                    parameters=params,
                    confidence=0.95,
                    raw_text=text,
                )

        return Intent(action="chat", parameters={"query": text}, confidence=0.5, raw_text=text)


intent_resolver = IntentResolver()
