"""Builtin agent tools for managing and triggering workflow macros and action pipelines."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from jarvis.macros.engine import MacroEngine
from jarvis.macros.models import MacroDefinition, MacroStep
from jarvis.macros.store import MacroStore

logger = logging.getLogger(__name__)

_GLOBAL_ENGINE: Optional[MacroEngine] = None


def _get_engine() -> MacroEngine:
    global _GLOBAL_ENGINE
    if _GLOBAL_ENGINE is None:
        _GLOBAL_ENGINE = MacroEngine()
    return _GLOBAL_ENGINE


def list_macros() -> str:
    """List all available automated workflow macros, their trigger phrases, and step counts."""
    engine = _get_engine()
    macros = engine.store.list_macros()
    if not macros:
        return "No workflow macros configured."

    lines = ["Configured Workflow Macros:"]
    for m in macros:
        status = "ENABLED" if m.enabled else "DISABLED"
        triggers_str = ", ".join(f"'{t}'" for t in m.triggers)
        lines.append(f"\n• {m.name} [{status}] ({len(m.steps)} steps)")
        lines.append(f"  Triggers: {triggers_str}")
        lines.append(f"  Description: {m.description}")
    return "\n".join(lines)


def run_macro(macro_name: str, variables: Optional[Dict[str, Any]] = None) -> str:
    """Trigger and execute an automated workflow macro by name with optional variables."""
    engine = _get_engine()
    res = engine.execute_macro(macro_name.strip(), variables=variables)
    if res.success:
        return f"Macro '{res.macro_name}' executed successfully ({res.steps_completed}/{res.total_steps} steps completed)."
    return f"Macro '{res.macro_name}' failed: {res.error}"


def create_multi_app_workflow(
    name: str,
    apps: List[str] | str,
    urls: Optional[List[str] | str] = None,
    initial_speech: Optional[str] = None,
    description: str = "",
) -> str:
    """Orchestrate and save a multi-application desktop workflow in one command."""
    from jarvis.macros.models import StepType
    engine = _get_engine()

    app_list = [a.strip() for a in (apps.split(",") if isinstance(apps, str) else apps) if a.strip()]
    url_list = []
    if urls:
        url_list = [u.strip() for u in (urls.split(",") if isinstance(urls, str) else urls) if u.strip()]

    steps: List[MacroStep] = []
    if initial_speech:
        steps.append(MacroStep(type=StepType.SPEAK, target=initial_speech.strip(), description="Initial voice announcement"))

    for app in app_list:
        steps.append(MacroStep(type=StepType.OPEN_APP, target=app, description=f"Launch {app}"))
        steps.append(MacroStep(type=StepType.PAUSE, target="1.0", description="Wait for app init"))

    for url in url_list:
        steps.append(MacroStep(type=StepType.OPEN_URL, target=url, description=f"Open {url}"))

    clean_name = name.strip().lower().replace(" ", "_")
    macro = MacroDefinition(
        name=clean_name,
        description=description or f"Multi-app workflow launching {', '.join(app_list)}",
        triggers=[clean_name.replace("_", " "), f"launch {clean_name.replace('_', ' ')}"],
        steps=steps,
        enabled=True,
    )
    engine.store.save_macro(macro)
    return f"Multi-app workflow '{clean_name}' created with {len(app_list)} apps and {len(url_list)} URLs ({len(steps)} steps)."


def start_recording_macro(name: str, description: str = "") -> str:
    """Start an interactive macro recording session to capture upcoming user actions."""
    from jarvis.macros.recorder import MacroRecorder
    recorder = MacroRecorder.get_instance(store=_get_engine().store)
    recorder.start_recording(name=name, description=description)
    return f"Macro recording session started for '{name}'. Perform actions or use record tools, then call stop_recording_macro."


def stop_recording_macro() -> str:
    """Finish the active macro recording session and save the captured workflow definition."""
    from jarvis.macros.recorder import MacroRecorder
    recorder = MacroRecorder.get_instance(store=_get_engine().store)
    macro_def = recorder.stop_recording(save=True)
    if not macro_def:
        return "No active macro recording session found."
    return f"Macro recording completed and saved as '{macro_def.name}' with {len(macro_def.steps)} steps."


def create_macro(
    name: str,
    triggers: List[str] | str,
    steps: List[Dict[str, Any]],
    description: str = "",
) -> str:
    """Create and save a new voice-activated workflow macro."""
    engine = _get_engine()
    
    if isinstance(triggers, str):
        trig_list = [t.strip() for t in triggers.split(",") if t.strip()]
    else:
        trig_list = [str(t).strip() for t in triggers if str(t).strip()]

    macro_steps = [MacroStep.from_dict(s) for s in steps]
    macro = MacroDefinition(
        name=name.strip().lower().replace(" ", "_"),
        description=description.strip(),
        triggers=trig_list,
        steps=macro_steps,
        enabled=True,
    )
    engine.store.save_macro(macro)
    return f"Workflow macro '{macro.name}' created with {len(macro.steps)} steps and {len(macro.triggers)} trigger(s)."


def delete_macro(name: str) -> str:
    """Delete a workflow macro by name."""
    engine = _get_engine()
    clean_name = name.strip().lower().replace(" ", "_")
    if engine.store.delete_macro(clean_name):
        return f"Macro '{clean_name}' deleted."
    return f"Macro '{clean_name}' not found."


def toggle_macro(name: str, enabled: bool) -> str:
    """Enable or disable a workflow macro."""
    engine = _get_engine()
    clean_name = name.strip().lower().replace(" ", "_")
    macro = engine.store.get_macro(clean_name)
    if not macro:
        return f"Macro '{clean_name}' not found."
    macro.enabled = enabled
    engine.store.save_macro(macro)
    state_str = "ENABLED" if enabled else "DISABLED"
    return f"Macro '{clean_name}' is now {state_str}."
