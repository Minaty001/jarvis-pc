"""Macro execution coordinator and trigger matcher."""

from __future__ import annotations

import asyncio
import logging
import re
import shlex
import subprocess  # nosec B404
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from jarvis.macros.models import MacroDefinition, MacroStep, StepType
from jarvis.macros.store import MacroStore
from jarvis.system.notifications import notify
from jarvis.tools.registry import ToolRegistry
from jarvis.voice.tts import speak

logger = logging.getLogger(__name__)


@dataclass
class MacroExecutionResult:
    macro_name: str
    success: bool
    steps_completed: int
    total_steps: int
    outputs: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None


class MacroEngine:
    """Executes multi-step automated macros and matches voice triggers."""

    def __init__(
        self,
        store: Optional[MacroStore] = None,
        tool_registry: Optional[ToolRegistry] = None,
    ):
        self.store = store or MacroStore()
        self.tool_registry = tool_registry

    def find_macro_by_trigger(self, phrase: str) -> Optional[MacroDefinition]:
        """Find an enabled macro matching a natural voice command."""
        clean_input = re.sub(r"[^\w\s]", "", phrase.lower()).strip()
        if not clean_input:
            return None

        for macro in self.store.list_macros():
            if not macro.enabled:
                continue
            for trig in macro.triggers:
                clean_trig = re.sub(r"[^\w\s]", "", trig.lower()).strip()
                if clean_trig and (clean_trig in clean_input or clean_input in clean_trig):
                    return macro
        return None

    def execute_step(self, step: MacroStep) -> Tuple[bool, Any]:
        """Execute a single macro action step."""
        try:
            if step.type == StepType.SPEAK:
                text = step.target.strip()
                if text:
                    speak(text)
                return True, text

            elif step.type == StepType.NOTIFY:
                title = step.target.strip() or "JARVIS Workflow"
                msg = step.args.get("message", title)
                urgency = step.args.get("urgency", "normal")
                ok = notify(title, msg, urgency=urgency)
                return ok, msg

            elif step.type == StepType.COMMAND:
                cmd_str = step.target.strip()
                if not cmd_str:
                    return False, "Empty command string"

                cmd_args = shlex.split(cmd_str)
                # Run command with timeout without shell execution for security audit compliance
                proc = subprocess.run(  # nosec B603
                    cmd_args,
                    capture_output=True,
                    text=True,
                    timeout=step.timeout,
                    check=False,
                )
                output = proc.stdout.strip() if proc.returncode == 0 else proc.stderr.strip()
                return proc.returncode == 0, output

            elif step.type == StepType.PAUSE:
                try:
                    sec = float(step.target) if step.target else float(step.args.get("seconds", 1.0))
                except (ValueError, TypeError):
                    sec = 1.0
                time.sleep(sec)
                return True, f"Paused {sec}s"

            elif step.type == StepType.OPEN_APP:
                from jarvis.tools.builtin.applications import open_application
                app_name = step.target.strip()
                msg = open_application(app_name)
                return True, msg

            elif step.type == StepType.OPEN_URL:
                from jarvis.tools.builtin.applications import open_url
                url_str = step.target.strip()
                msg = open_url(url_str)
                return True, msg

            elif step.type == StepType.TOOL:
                tool_name = step.target.strip()
                args = step.args or {}
                if self.tool_registry and hasattr(self.tool_registry, "execute"):
                    res = asyncio.run(self.tool_registry.execute(tool_name, args))
                    return True, str(res)
                return False, f"ToolRegistry unavailable for tool '{tool_name}'"

            else:
                return False, f"Unsupported step type: {step.type}"

        except Exception as exc:
            logger.warning("Macro step execution error: %s", exc)
            return False, str(exc)

    def execute_macro(
        self,
        macro: MacroDefinition | str,
        on_step: Optional[Callable[[int, MacroStep, str], None]] = None,
    ) -> MacroExecutionResult:
        """Sequentially execute all steps in the macro pipeline."""
        if isinstance(macro, str):
            found = self.store.get_macro(macro)
            if not found:
                return MacroExecutionResult(
                    macro_name=macro,
                    success=False,
                    steps_completed=0,
                    total_steps=0,
                    error=f"Macro '{macro}' not found.",
                )
            macro_obj = found
        else:
            macro_obj = macro

        total = len(macro_obj.steps)
        completed = 0
        outputs = []

        logger.info("Executing macro '%s' (%d steps)", macro_obj.name, total)

        for i, step in enumerate(macro_obj.steps, start=1):
            success, output = self.execute_step(step)
            outputs.append(
                {
                    "step_index": i,
                    "type": step.type.value,
                    "target": step.target,
                    "success": success,
                    "output": output,
                }
            )

            if on_step:
                try:
                    on_step(i, step, str(output))
                except Exception:
                    pass

            if not success and not step.ignore_errors:
                logger.warning("Macro '%s' aborted at step %d: %s", macro_obj.name, i, output)
                return MacroExecutionResult(
                    macro_name=macro_obj.name,
                    success=False,
                    steps_completed=completed,
                    total_steps=total,
                    outputs=outputs,
                    error=f"Failed at step #{i} ({step.type.value}: {step.target}): {output}",
                )

            completed += 1

        logger.info("Macro '%s' completed successfully (%d/%d steps)", macro_obj.name, completed, total)
        return MacroExecutionResult(
            macro_name=macro_obj.name,
            success=True,
            steps_completed=completed,
            total_steps=total,
            outputs=outputs,
        )
