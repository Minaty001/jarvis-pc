"""Builtin tools for listing and switching voice personalities and acoustic tuning."""

from __future__ import annotations

import logging
from typing import Optional

from jarvis.voice.profiles import VOICE_PROFILES, get_profile_manager

logger = logging.getLogger(__name__)


def list_voice_profiles() -> str:
    """List all available neural voice personality presets and languages."""
    mgr = get_profile_manager()
    profiles = mgr.list_profiles()
    lines = ["Available Voice Personalities:"]
    for p in profiles:
        active_marker = " [ACTIVE]" if p["key"] == mgr.active_key else ""
        lines.append(f"• {p['key']:<16} | {p['name']} ({p['language']}){active_marker}")
        lines.append(f"  └─ {p['description']}")
    return "\n".join(lines)


def set_voice_profile(profile_name: str) -> str:
    """Switch active JARVIS voice personality (e.g. 'british_butler', 'classic_jarvis', 'tactical_ai', 'indian_english', 'hindi_assistant')."""
    mgr = get_profile_manager()
    key = profile_name.strip().lower()
    try:
        prof = mgr.set_profile(key)
        return f"Voice personality switched to '{prof.name}' ({prof.voice_id}, rate: {prof.rate}, pitch: {prof.pitch})."
    except ValueError:
        available = ", ".join(VOICE_PROFILES.keys())
        return f"Unknown voice profile '{profile_name}'. Available: {available}"


def tune_voice_acoustics(rate: Optional[str] = None, pitch: Optional[str] = None) -> str:
    """Tune speech rate (e.g. '+10%', '-5%') and pitch (e.g. '-4Hz', '+5Hz') for the active voice profile."""
    mgr = get_profile_manager()
    active = mgr.get_active_profile()
    if rate:
        active.rate = rate
    if pitch:
        active.pitch = pitch
    return f"Acoustic tuning applied to '{active.name}': rate={active.rate}, pitch={active.pitch}."


def toggle_auto_wake(enabled: bool) -> str:
    """Enable or disable ambient background wake word listening."""
    from jarvis.config.settings import get_settings
    settings = get_settings()
    settings.auto_wake_word = enabled
    state_str = "ENABLED" if enabled else "DISABLED"
    return f"Ambient Auto Wake Word has been {state_str}. Trigger phrases: '{settings.wake_phrases}'."


def configure_wake_word(phrases: Optional[str] = None, ack_phrase: Optional[str] = None) -> str:
    """Configure wake word trigger phrases (comma-separated, e.g. 'hey jarvis,jarvis,computer') and acknowledgment phrase (e.g. 'Yes, sir?')."""
    from jarvis.config.settings import get_settings
    settings = get_settings()
    updated = []
    if phrases is not None:
        settings.wake_phrases = phrases.strip().lower()
        updated.append(f"wake phrases='{settings.wake_phrases}'")
    if ack_phrase is not None:
        settings.wake_ack_phrase = ack_phrase.strip()
        updated.append(f"ack phrase='{settings.wake_ack_phrase}'")
    
    return f"Wake word configuration updated: {', '.join(updated) if updated else 'no changes'}."
