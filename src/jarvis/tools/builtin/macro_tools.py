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


def run_macro(macro_name: str) -> str:
    """Trigger and execute an automated workflow macro by name."""
    engine = _get_engine()
    res = engine.execute_macro(macro_name.strip())
    if res.success:
        return f"Macro '{res.macro_name}' executed successfully ({res.steps_completed}/{res.total_steps} steps completed)."
    return f"Macro '{res.macro_name}' failed: {res.error}"


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
