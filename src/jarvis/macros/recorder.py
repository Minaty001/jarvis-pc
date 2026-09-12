"""Interactive Macro Recording Service for JARVIS PC."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from jarvis.macros.models import MacroDefinition, MacroStep, StepType
from jarvis.macros.store import MacroStore

logger = logging.getLogger(__name__)


class MacroRecorder:
    """Session-based recorder for assembling user actions into reusable MacroDefinitions."""

    _instance: Optional[MacroRecorder] = None

    def __init__(self, store: Optional[MacroStore] = None) -> None:
        self.store = store or MacroStore()
        self._is_recording: bool = False
        self._macro_name: str = ""
        self._description: str = ""
        self._triggers: List[str] = []
        self._steps: List[MacroStep] = []
        self._start_time: float = 0.0

    @classmethod
    def get_instance(cls, store: Optional[MacroStore] = None) -> MacroRecorder:
        if cls._instance is None:
            cls._instance = cls(store=store)
        return cls._instance

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    def start_recording(
        self,
        name: str,
        description: str = "",
        triggers: Optional[List[str]] = None,
    ) -> bool:
        """Initialize a new recording session."""
        self._macro_name = name.strip()
        self._description = description.strip()
        self._triggers = triggers or [name.lower().replace("_", " ")]
        self._steps = []
        self._start_time = time.time()
        self._is_recording = True
        logger.info("Macro recording session started for '%s'", self._macro_name)
        return True

    def record_step(self, step: MacroStep | Dict[str, Any]) -> bool:
        """Append an action step to the active recording session."""
        if not self._is_recording:
            logger.warning("Attempted to record step while recorder is inactive.")
            return False

        if isinstance(step, dict):
            macro_step = MacroStep.from_dict(step)
        else:
            macro_step = step

        self._steps.append(macro_step)
        logger.debug("Recorded macro step #%d: %s (%s)", len(self._steps), macro_step.type.value, macro_step.target)
        return True

    def record_command(self, command: str, description: str = "") -> bool:
        return self.record_step(
            MacroStep(
                type=StepType.COMMAND,
                target=command,
                description=description or f"Run command: {command}",
            )
        )

    def record_app(self, app_name: str, description: str = "") -> bool:
        return self.record_step(
            MacroStep(
                type=StepType.OPEN_APP,
                target=app_name,
                description=description or f"Launch application: {app_name}",
            )
        )

    def record_url(self, url: str, description: str = "") -> bool:
        return self.record_step(
            MacroStep(
                type=StepType.OPEN_URL,
                target=url,
                description=description or f"Open URL: {url}",
            )
        )

    def record_ui_click(self, x: int, y: int, button: str = "left", description: str = "") -> bool:
        return self.record_step(
            MacroStep(
                type=StepType.MOUSE_CLICK,
                target=f"{x},{y}",
                args={"x": x, "y": y, "button": button},
                description=description or f"Click ({x}, {y})",
            )
        )

    def record_ui_text(self, text: str, description: str = "") -> bool:
        return self.record_step(
            MacroStep(
                type=StepType.TYPE_TEXT,
                target=text,
                args={"text": text},
                description=description or f"Type text ({len(text)} chars)",
            )
        )

    def record_ui_hotkey(self, combo: str, description: str = "") -> bool:
        return self.record_step(
            MacroStep(
                type=StepType.KEY_COMBO,
                target=combo,
                args={"combo": combo},
                description=description or f"Press hotkey: {combo}",
            )
        )

    def stop_recording(self, save: bool = True) -> Optional[MacroDefinition]:
        """Finalize the active recording session and optionally persist the MacroDefinition."""
        if not self._is_recording:
            return None

        macro_def = MacroDefinition(
            name=self._macro_name,
            description=self._description,
            triggers=self._triggers,
            steps=list(self._steps),
            created_at=int(self._start_time),
        )

        if save:
            self.store.save_macro(macro_def)
            logger.info("Macro '%s' saved with %d recorded steps", macro_def.name, len(macro_def.steps))

        self._is_recording = False
        self._steps = []
        self._macro_name = ""
        self._description = ""
        self._triggers = []
        return macro_def

    def get_active_session(self) -> Optional[Dict[str, Any]]:
        """Return information about the active recording session."""
        if not self._is_recording:
            return None
        return {
            "name": self._macro_name,
            "description": self._description,
            "triggers": self._triggers,
            "step_count": len(self._steps),
            "elapsed_seconds": round(time.time() - self._start_time, 1),
            "steps": [s.to_dict() for s in self._steps],
        }
