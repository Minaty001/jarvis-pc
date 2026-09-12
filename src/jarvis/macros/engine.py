"""Macro execution coordinator and trigger matcher."""

from __future__ import annotations

import asyncio
import logging
import os
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


def render_template(val: Any, variables: Dict[str, Any]) -> Any:
    """Recursively resolve {{variable}} placeholders in strings, dictionaries, or lists."""
    if isinstance(val, str):
        res = val
        # Built-in context variables
        builtins = {
            "date": time.strftime("%Y-%m-%d"),
            "time": time.strftime("%H:%M:%S"),
            "home": os.path.expanduser("~"),
            "user": os.environ.get("USER", "user"),
        }
        all_vars = {**builtins, **variables}
        for k, v in all_vars.items():
            pattern = re.compile(r"\{\{\s*" + re.escape(k) + r"\s*\}\}|\{" + re.escape(k) + r"\}")
            res = pattern.sub(str(v), res)
        return res
    elif isinstance(val, dict):
        return {k: render_template(v, variables) for k, v in val.items()}
    elif isinstance(val, list):
        return [render_template(item, variables) for item in val]
    return val


@dataclass
class MacroExecutionResult:
    macro_name: str
    success: bool
    steps_completed: int
    total_steps: int
    outputs: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None


class MacroEngine:
    """Executes multi-step automated macros, resolves parameters, and matches triggers."""

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

    def execute_step(
        self,
        step: MacroStep,
        variables: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Any]:
        """Execute a single macro action step with optional retry policy."""
        vars_dict = variables or {}
        target = str(render_template(step.target, vars_dict))
        args = render_template(step.args, vars_dict) if step.args else {}

        attempts = 1 + max(0, step.retries)
        last_error = ""

        for attempt in range(attempts):
            try:
                if step.type == StepType.SPEAK:
                    text = target.strip()
                    if text:
                        speak(text)
                    return True, text

                elif step.type == StepType.NOTIFY:
                    title = target.strip() or "JARVIS Workflow"
                    msg = args.get("message", title)
                    urgency = args.get("urgency", "normal")
                    ok = notify(title, msg, urgency=urgency)
                    return ok, msg

                elif step.type == StepType.COMMAND:
                    cmd_str = target.strip()
                    if not cmd_str:
                        return False, "Empty command string"

                    cmd_args = shlex.split(cmd_str)
                    proc = subprocess.run(  # nosec B603
                        cmd_args,
                        capture_output=True,
                        text=True,
                        timeout=step.timeout,
                        check=False,
                    )
                    output = proc.stdout.strip() if proc.returncode == 0 else proc.stderr.strip()
                    if proc.returncode == 0:
                        return True, output
                    last_error = output or f"Command exited with code {proc.returncode}"

                elif step.type == StepType.PAUSE:
                    try:
                        sec = float(target) if target else float(args.get("seconds", 1.0))
                    except (ValueError, TypeError):
                        sec = 1.0
                    time.sleep(sec)
                    return True, f"Paused {sec}s"

                elif step.type == StepType.OPEN_APP:
                    from jarvis.tools.builtin.applications import open_application
                    app_name = target.strip()
                    msg = open_application(app_name)
                    return True, msg

                elif step.type == StepType.OPEN_URL:
                    from jarvis.tools.builtin.applications import open_url
                    url_str = target.strip()
                    msg = open_url(url_str)
                    return True, msg

                elif step.type == StepType.MOUSE_CLICK:
                    from jarvis.tools.builtin.desktop_automation import click_mouse
                    x = int(args.get("x", 0)) if "x" in args else 0
                    y = int(args.get("y", 0)) if "y" in args else 0
                    button = str(args.get("button", "left"))
                    count = int(args.get("count", 1))
                    res = asyncio.run(click_mouse(x=x, y=y, button=button, clicks=count))
                    return True, res

                elif step.type == StepType.MOUSE_MOVE:
                    from jarvis.tools.builtin.desktop_automation import move_mouse
                    x = int(args.get("x", target or 0))
                    y = int(args.get("y", 0))
                    res = asyncio.run(move_mouse(x=x, y=y))
                    return True, res

                elif step.type == StepType.TYPE_TEXT:
                    from jarvis.tools.builtin.desktop_automation import type_text
                    text = target or str(args.get("text", ""))
                    res = asyncio.run(type_text(text))
                    return True, res

                elif step.type == StepType.KEY_COMBO:
                    from jarvis.tools.builtin.desktop_automation import press_key
                    combo = target or str(args.get("combo", ""))
                    res = asyncio.run(press_key(combo))
                    return True, res

                elif step.type == StepType.FOCUS_WINDOW:
                    from jarvis.tools.builtin.desktop_automation import focus_window
                    title = target or str(args.get("title", ""))
                    res = asyncio.run(focus_window(title))
                    return True, res

                elif step.type == StepType.WAIT_FOR_WINDOW:
                    from jarvis.system.process import run_process
                    title = (target or str(args.get("title", ""))).lower()
                    deadline = time.time() + float(step.timeout or 10.0)
                    found = False
                    while time.time() < deadline:
                        # Check window list using wmctrl
                        res = asyncio.run(run_process(["wmctrl", "-l"], timeout=2.0))
                        if res.success and title in res.stdout.lower():
                            found = True
                            break
                        time.sleep(0.5)
                    if found:
                        return True, f"Window '{title}' detected"
                    last_error = f"Timed out waiting for window matching '{title}'"

                elif step.type == StepType.ASSERT_PROCESS:
                    from jarvis.tools.builtin.processes import find_processes
                    proc_name = target or str(args.get("name", ""))
                    matches = find_processes(name=proc_name)
                    if matches:
                        return True, f"Process '{proc_name}' is running ({len(matches)} instance(s))"
                    last_error = f"Process '{proc_name}' is not running"

                elif step.type == StepType.TOOL:
                    tool_name = target.strip()
                    if self.tool_registry and hasattr(self.tool_registry, "execute"):
                        res = asyncio.run(self.tool_registry.execute(tool_name, args))
                        return True, str(res)
                    return False, f"ToolRegistry unavailable for tool '{tool_name}'"

                else:
                    return False, f"Unsupported step type: {step.type}"

            except Exception as exc:
                last_error = str(exc)
                logger.warning("Macro step execution error (attempt %d/%d): %s", attempt + 1, attempts, exc)

            if attempt < attempts - 1:
                time.sleep(0.5)

        return False, last_error or "Step failed"

    def execute_macro(
        self,
        macro: MacroDefinition | str,
        variables: Optional[Dict[str, Any]] = None,
        on_step: Optional[Callable[[int, MacroStep, str], None]] = None,
    ) -> MacroExecutionResult:
        """Sequentially execute all steps in the macro pipeline with variable substitution."""
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

        # Merge macro default variables with runtime override variables
        merged_vars = {**(macro_obj.variables or {}), **(variables or {})}
        total = len(macro_obj.steps)
        completed = 0
        outputs = []

        logger.info("Executing macro '%s' (%d steps)", macro_obj.name, total)

        for i, step in enumerate(macro_obj.steps, start=1):
            success, output = self.execute_step(step, variables=merged_vars)
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
