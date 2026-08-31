"""
Intent Resolver — Parse user text into structured intent.
Uses pattern matching for fast local resolution, LLM for complex cases.

Supports English and Hinglish (Hindi written in Latin script).
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


def clean_conversational_fillers(text: str) -> str:
    """Strip leading conversational fillers (e.g. 'ek kaam karo pehle', 'pls', 'suno')."""
    cleaned = re.sub(
        r"^(?:ek\s+kaam\s+karo\s+|pehle\s+|pls\s+|please\s+|suno\s+|jarvis\s+)+",
        "", text, flags=re.IGNORECASE,
    ).strip()
    return cleaned


# ── Pattern-based intent mappings ────────────────────────────────────────────
PATTERNS = [
    # ── YouTube play (English + Hinglish) ────────────────────────────────
    (r"play\s+(.+?)\s+on\s+youtube",
        lambda m: ("play_on_youtube", {"query": m.group(1).strip()})),
    (r"youtube\s+(?:pe|par|mein|on)?\s*(.+?)\s+(?:chalao|play|bajao|lagao|chala)$",
        lambda m: ("play_on_youtube", {"query": m.group(1).strip()})),
    (r"(?:chalao|play|bajao|lagao)\s+(.+?)\s+(?:youtube\s+(?:pe|par|mein|on)|on\s+youtube)$",
        lambda m: ("play_on_youtube", {"query": m.group(1).strip()})),
    (r"youtube\s+pe\s+(.+?)(?:\s+(?:chalao|play|bajao|lagao))?$",
        lambda m: ("play_on_youtube", {"query": m.group(1).strip()})),
    (r"search\s+youtube\s+(?:for\s+)?(.+)",
        lambda m: ("play_on_youtube", {"query": m.group(1).strip()})),

    # ── Spotify play ─────────────────────────────────────────────────────
    (r"play\s+(.+?)\s+on\s+spotify",
        lambda m: ("play_on_spotify", {"query": m.group(1).strip()})),
    (r"spotify\s+(?:pe|par|mein|on)?\s*(.+?)\s+(?:chalao|play|bajao|lagao|chala)$",
        lambda m: ("play_on_spotify", {"query": m.group(1).strip()})),

    # ── App control ───────────────────────────────────────────────────────
    (r"open\s+(.+)",     lambda m: ("open_app",  {"app_name": m.group(1).strip()})),
    (r"launch\s+(.+)",   lambda m: ("open_app",  {"app_name": m.group(1).strip()})),
    (r"start\s+(.+)",    lambda m: ("open_app",  {"app_name": m.group(1).strip()})),
    (r"close\s+(.+)",    lambda m: ("close_app", {"app_name": m.group(1).strip()})),
    (r"quit\s+(.+)",     lambda m: ("close_app", {"app_name": m.group(1).strip()})),
    (r"kill\s+(.+)",     lambda m: ("close_app", {"app_name": m.group(1).strip()})),
    (r"band\s+karo\s+(.+)", lambda m: ("close_app", {"app_name": m.group(1).strip()})),
    (r"(.+)\s+(?:kholo|kholdo|open\s+karo)", lambda m: ("open_app", {"app_name": m.group(1).strip()})),

    # ── System info ───────────────────────────────────────────────────────
    (r"what(?:'s| is)(?: the)? time|current time|kitna baja|time batao",
        lambda m: ("get_time", {})),
    (r"what(?:'s| is)(?: the)? date|today(?:'s| is)(?: the)? date|aaj ki date",
        lambda m: ("get_date", {})),
    (r"battery|battery level|battery status|kitni battery",
        lambda m: ("get_battery", {})),
    (r"cpu|cpu usage|processor",     lambda m: ("get_cpu", {})),
    (r"memory|ram|memory usage",     lambda m: ("get_memory", {})),
    (r"disk|storage|disk space",     lambda m: ("get_disk", {})),
    (r"network|internet|ip address", lambda m: ("get_network", {})),

    # ── File operations ───────────────────────────────────────────────────
    (r"list files?\s*(?:in\s+)?(.+)?",          lambda m: ("list_files",  {"path": (m.group(1) or ".").strip()})),
    (r"create (?:a )?file\s+(.+)",              lambda m: ("create_file", {"path": m.group(1).strip()})),
    (r"delete (?:a )?file\s+(.+)",              lambda m: ("delete_file", {"path": m.group(1).strip()})),

    # ── Web search ────────────────────────────────────────────────────────
    (r"search\s+(?:for\s+)?(.+)",               lambda m: ("web_search", {"query": m.group(1).strip()})),
    (r"google\s+(.+)",                           lambda m: ("web_search", {"query": m.group(1).strip()})),
    (r"dhundho\s+(.+)|(.+)\s+dhundho",          lambda m: ("web_search", {"query": (m.group(1) or m.group(2)).strip()})),
    (r"(.+)\s+(?:dikhao|dikha\s+do|show)",     lambda m: ("web_search", {"query": m.group(1).strip()})),

    # ── Screenshot ───────────────────────────────────────────────────────
    (r"screenshot|take (?:a )?screenshot|capture screen|screen capture",
        lambda m: ("screenshot", {})),

    # ── Clipboard ────────────────────────────────────────────────────────
    (r"copy\s+(.+)",     lambda m: ("clipboard_copy",  {"text": m.group(1).strip()})),
    (r"paste|what(?:'s| is) (?:on |in )?my clipboard",
        lambda m: ("clipboard_paste", {})),

    # ── Volume ───────────────────────────────────────────────────────────
    (r"volume\s+(up|down|higher|lower|\d+)(?:\s*%)?",
        lambda m: ("set_volume", {"level": m.group(1)})),
    (r"mute|sound off",  lambda m: ("set_volume", {"level": "mute"})),
    (r"volume\s+(?:up|badha(?:o)?)",            lambda m: ("set_volume", {"level": "up"})),
    (r"volume\s+(?:down|ghata(?:o)?|kam)",      lambda m: ("set_volume", {"level": "down"})),

    # ── Media general ─────────────────────────────────────────────────────
    (r"play\s+(.+)",     lambda m: ("media_play", {"query": m.group(1).strip()})),
    (r"pause|stop (?:music|video|media)|ruko",  lambda m: ("media_pause", {})),

    # ── Shell ─────────────────────────────────────────────────────────────
    (r"run\s+(?:command\s+)?(.+)",   lambda m: ("shell_exec", {"command": m.group(1).strip()})),
    (r"execute\s+(.+)",              lambda m: ("shell_exec", {"command": m.group(1).strip()})),

    # ── Git ───────────────────────────────────────────────────────────────
    (r"git status",              lambda m: ("git_status",  {})),
    (r"git commit\s+(.+)",       lambda m: ("git_commit",  {"message": m.group(1).strip()})),
    (r"git push",                lambda m: ("git_push",    {})),
    (r"git pull",                lambda m: ("git_pull",    {})),

    # ── Docker ────────────────────────────────────────────────────────────
    (r"docker (?:list )?containers?",   lambda m: ("docker_ps",    {})),
    (r"docker images",                  lambda m: ("docker_images", {})),
    (r"docker (?:start|run)\s+(.+)",    lambda m: ("docker_start", {"container": m.group(1).strip()})),
    (r"docker stop\s+(.+)",             lambda m: ("docker_stop",  {"container": m.group(1).strip()})),
]


class IntentResolver:
    """Resolve user text to structured intent using ordered pattern list."""

    def resolve(self, text: str) -> Intent:
        cleaned = clean_conversational_fillers(text)
        text_lower = cleaned.lower().strip()

        for pattern, handler in PATTERNS:
            match = re.search(pattern, text_lower)
            if match:
                action, params = handler(match)
                # Clean up empty/None params
                params = {k: v for k, v in params.items() if v is not None and v != ""}
                return Intent(
                    action=action,
                    parameters=params,
                    confidence=0.95,
                    raw_text=text,
                )

        return Intent(action="chat", parameters={"query": text}, confidence=0.5, raw_text=text)


intent_resolver = IntentResolver()
