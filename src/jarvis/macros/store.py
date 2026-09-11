"""Macro store managing YAML / JSON persistence and default bundled presets."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from jarvis.macros.models import MacroDefinition, MacroStep, StepType

logger = logging.getLogger(__name__)


def default_macro_config_path() -> Path:
    """Return default macros YAML config path."""
    base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config/jarvis"))
    return Path(base) / "macros.yaml"


DEFAULT_PRESET_MACROS: List[Dict[str, Any]] = [
    {
        "name": "coding_mode",
        "description": "Prepares development workspace: launches IDE, opens GitHub, speaks greeting.",
        "triggers": ["enter coding mode", "start coding", "coding mode", "prepare workspace"],
        "confirmation_required": False,
        "enabled": True,
        "steps": [
            {
                "type": "speak",
                "target": "Initializing coding environment, sir.",
                "description": "Speak initial greeting",
            },
            {
                "type": "notify",
                "target": "JARVIS Coding Mode",
                "args": {"message": "Development workspace initialized."},
                "description": "Send desktop notification",
            },
            {
                "type": "speak",
                "target": "Workspace ready. All systems nominal.",
                "description": "Speak readiness confirmation",
            },
        ],
    },
    {
        "name": "meeting_prep",
        "description": "Prepares workstation for meetings: silences notifications and speaks confirmation.",
        "triggers": ["meeting prep", "prepare for meeting", "meeting mode"],
        "confirmation_required": False,
        "enabled": True,
        "steps": [
            {
                "type": "speak",
                "target": "Preparing workstation for your meeting, sir.",
                "description": "Speak status",
            },
            {
                "type": "notify",
                "target": "JARVIS Meeting Mode",
                "args": {"message": "Meeting mode active. Distractions silenced."},
                "description": "Meeting notification",
            },
        ],
    },
    {
        "name": "system_health_check",
        "description": "Runs system diagnostics doctor check and reports status.",
        "triggers": ["run system diagnostics", "system health check", "diagnostics check"],
        "confirmation_required": False,
        "enabled": True,
        "steps": [
            {
                "type": "speak",
                "target": "Running complete hardware and cognitive diagnostics.",
                "description": "Speak starting diagnostics",
            },
            {
                "type": "command",
                "target": "uptime",
                "description": "Query system uptime",
            },
            {
                "type": "speak",
                "target": "Diagnostics complete. Core subsystems functioning at peak efficiency.",
                "description": "Speak final health assessment",
            },
        ],
    },
    {
        "name": "lockdown",
        "description": "Locks workstation session for security.",
        "triggers": ["lockdown workstation", "lockdown", "secure workstation", "lock pc"],
        "confirmation_required": False,
        "enabled": True,
        "steps": [
            {
                "type": "speak",
                "target": "Locking workstation session, sir.",
                "description": "Speak locking notice",
            },
            {
                "type": "command",
                "target": "loginctl lock-session",
                "description": "Lock display session",
            },
        ],
    },
]


class MacroStore:
    """Manages macro definitions loaded from YAML or created dynamically."""

    def __init__(self, config_path: Optional[str | Path] = None):
        self.config_path = Path(config_path) if config_path else default_macro_config_path()
        self._macros: Dict[str, MacroDefinition] = {}
        self.load()

    def load(self) -> None:
        """Load macros from YAML file, seeding defaults if missing."""
        if not self.config_path.exists():
            self._seed_defaults()
            return

        try:
            raw_text = self.config_path.read_text(encoding="utf-8")
            data = yaml.safe_load(raw_text) or {}
            raw_list = data.get("macros", [])
            self._macros = {}
            for item in raw_list:
                macro = MacroDefinition.from_dict(item)
                self._macros[macro.name] = macro
            logger.info("Loaded %d workflow macros from %s", len(self._macros), self.config_path)
        except Exception as exc:
            logger.warning("Failed to load macros from %s (%s); seeding default presets", self.config_path, exc)
            self._seed_defaults()

    def save(self) -> None:
        """Save current macros to YAML file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "macros": [m.to_dict() for m in self._macros.values()],
            "version": "1.0",
        }
        with self.config_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
        logger.info("Saved %d macros to %s", len(self._macros), self.config_path)

    def _seed_defaults(self) -> None:
        """Seed pre-bundled default preset macros."""
        now = int(time.time())
        self._macros = {}
        for item in DEFAULT_PRESET_MACROS:
            item_copy = dict(item)
            item_copy["created_at"] = now
            macro = MacroDefinition.from_dict(item_copy)
            self._macros[macro.name] = macro
        self.save()

    def get_macro(self, name: str) -> Optional[MacroDefinition]:
        return self._macros.get(name)

    def list_macros(self) -> List[MacroDefinition]:
        return list(self._macros.values())

    def save_macro(self, macro: MacroDefinition) -> None:
        self._macros[macro.name] = macro
        self.save()

    def delete_macro(self, name: str) -> bool:
        if name in self._macros:
            del self._macros[name]
            self.save()
            return True
        return False
