"""JARVIS UI theme — Linux Mint / Cinnamon friendly dark palette, theme presets, and GTK CSS."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

THEMES: Dict[str, Dict[str, Any]] = {
    "arc_reactor": {
        "name": "Arc Reactor (Default)",
        "palette": {
            "bg": "#0b0f1a",
            "bg_panel": "#111726",
            "bg_elev": "#172033",
            "border": "#26344f",
            "text": "#e8f0ff",
            "text_dim": "#8fa3c4",
            "accent": "#3fd0ff",
            "accent2": "#2f7bff",
            "good": "#39e0a0",
            "warn": "#ffcf5c",
            "bad": "#ff5c7a",
            "speaking": "#7c9bff",
        },
        "orb_states": {
            "idle": "#39e0a0",
            "listening": "#3fd0ff",
            "thinking": "#ffcf5c",
            "speaking": "#7c9bff",
            "working": "#3fd0ff",
            "error": "#ff5c7a",
        },
    },
    "stark_gold": {
        "name": "Stark Mark VII (Crimson & Gold)",
        "palette": {
            "bg": "#12080a",
            "bg_panel": "#200e12",
            "bg_elev": "#2d141a",
            "border": "#4f2029",
            "text": "#fff4e8",
            "text_dim": "#c4a38f",
            "accent": "#ffd03f",
            "accent2": "#e63946",
            "good": "#ffd03f",
            "warn": "#ff9f1c",
            "bad": "#e63946",
            "speaking": "#ffb703",
        },
        "orb_states": {
            "idle": "#ffd03f",
            "listening": "#ffb703",
            "thinking": "#ff9f1c",
            "speaking": "#e63946",
            "working": "#ffd03f",
            "error": "#d62828",
        },
    },
    "cyberpunk": {
        "name": "Cyberpunk Neon (Violet & Pink)",
        "palette": {
            "bg": "#0d0914",
            "bg_panel": "#181024",
            "bg_elev": "#241836",
            "border": "#452b6b",
            "text": "#f7e8ff",
            "text_dim": "#b58fc4",
            "accent": "#f72585",
            "accent2": "#7209b7",
            "good": "#4cc9f0",
            "warn": "#f72585",
            "bad": "#e63946",
            "speaking": "#b5179e",
        },
        "orb_states": {
            "idle": "#4cc9f0",
            "listening": "#f72585",
            "thinking": "#b5179e",
            "speaking": "#7209b7",
            "working": "#4cc9f0",
            "error": "#e63946",
        },
    },
    "quantum_emerald": {
        "name": "Quantum Matrix (Emerald & Mint)",
        "palette": {
            "bg": "#08120c",
            "bg_panel": "#0e2015",
            "bg_elev": "#142d1e",
            "border": "#1d472f",
            "text": "#e8fff2",
            "text_dim": "#8fc4a3",
            "accent": "#00f5d4",
            "accent2": "#00bbf9",
            "good": "#00f5d4",
            "warn": "#fee440",
            "bad": "#f15bb5",
            "speaking": "#00bbf9",
        },
        "orb_states": {
            "idle": "#00f5d4",
            "listening": "#00bbf9",
            "thinking": "#fee440",
            "speaking": "#00f5d4",
            "working": "#00bbf9",
            "error": "#f15bb5",
        },
    },
}

_ACTIVE_THEME = "arc_reactor"

PALETTE = THEMES["arc_reactor"]["palette"]
ORB_STATES = THEMES["arc_reactor"]["orb_states"]


class ThemeManager:
    """Manages active theme presets, dynamic CSS styling, and runtime palette queries."""

    def __init__(self, default_theme: str = "arc_reactor"):
        self.active_theme = default_theme if default_theme in THEMES else "arc_reactor"

    def set_theme(self, theme_key: str) -> bool:
        """Switch active theme and reload GTK CSS."""
        global _ACTIVE_THEME, PALETTE, ORB_STATES
        if theme_key not in THEMES:
            logger.warning("Theme '%s' not found", theme_key)
            return False

        self.active_theme = theme_key
        _ACTIVE_THEME = theme_key
        PALETTE = THEMES[theme_key]["palette"]
        ORB_STATES = THEMES[theme_key]["orb_states"]
        load_css(self.active_theme)
        return True

    def get_palette(self) -> Dict[str, str]:
        return THEMES[self.active_theme]["palette"]

    def get_orb_states(self) -> Dict[str, str]:
        return THEMES[self.active_theme]["orb_states"]

    def list_themes(self) -> Dict[str, str]:
        return {k: v["name"] for k, v in THEMES.items()}


_THEME_MANAGER = ThemeManager()


def get_theme_manager() -> ThemeManager:
    return _THEME_MANAGER


def hex_to_rgba(hex_str: str, alpha: float = 1.0) -> Tuple[float, float, float, float]:
    """Convert hex string (e.g. #3fd0ff or 3fd0ff) to (r, g, b, a) float tuple in [0.0, 1.0]."""
    h = hex_str.lstrip("#")
    if len(h) != 6:
        return (0.0, 0.0, 0.0, alpha)
    r = int(h[0:2], 16) / 255.0
    g = int(h[2:4], 16) / 255.0
    b = int(h[4:6], 16) / 255.0
    return (r, g, b, alpha)


def css(theme_name: Optional[str] = None) -> str:
    """Return GTK CSS styling string for the given or currently active theme."""
    t_key = theme_name or _ACTIVE_THEME
    p = THEMES.get(t_key, THEMES["arc_reactor"])["palette"]
    return f"""
    window, .background {{
        background-color: {p['bg']};
    }}
    .jarvis-surface {{
        background-color: {p['bg_panel']};
        border: 1px solid {p['border']};
        border-radius: 12px;
    }}
    .jarvis-elev {{
        background-color: {p['bg_elev']};
        border: 1px solid {p['border']};
        border-radius: 10px;
    }}
    label.title {{
        color: {p['text']};
        font-weight: 700;
        font-size: 15px;
    }}
    label.subtle {{
        color: {p['text_dim']};
        font-size: 11px;
    }}
    label.accent {{
        color: {p['accent']};
        font-weight: 600;
    }}
    .orb-frame {{
        background-color: {p['bg']};
        border-radius: 16px;
    }}
    .chat-scroll {{
        background-color: {p['bg']};
    }}
    .chat-user {{
        background-color: {p['accent2']};
        color: #ffffff;
        border-radius: 12px;
        padding: 8px 12px;
    }}
    .chat-jarvis {{
        background-color: {p['bg_elev']};
        color: {p['text']};
        border: 1px solid {p['border']};
        border-radius: 12px;
        padding: 8px 12px;
    }}
    .chat-sys {{
        color: {p['text_dim']};
        font-size: 11px;
        font-style: italic;
    }}
    textview, textview text {{
        background-color: {p['bg_elev']};
        color: {p['text']};
        border-radius: 8px;
    }}
    entry {{
        background-color: {p['bg_elev']};
        color: {p['text']};
        border: 1px solid {p['border']};
        border-radius: 8px;
        padding: 6px 10px;
    }}
    entry:focus {{
        border: 1px solid {p['accent']};
    }}
    button {{
        background-color: {p['bg_elev']};
        color: {p['text']};
        border: 1px solid {p['border']};
        border-radius: 8px;
        padding: 6px 14px;
    }}
    button:hover {{
        background-color: #1d2b44;
        border: 1px solid {p['accent']};
    }}
    button.suggested-action {{
        background-color: {p['accent2']};
        color: #ffffff;
        border: none;
    }}
    button.suggested-action:hover {{
        background-color: #3f8cff;
    }}
    progressbar trough {{
        background-color: {p['bg_elev']};
        border-radius: 6px;
        min-height: 8px;
    }}
    progressbar progress {{
        background-color: {p['accent']};
        border-radius: 6px;
    }}
    .floating-orb {{
        background-color: transparent;
    }}
    """


def load_css(theme_name: Optional[str] = None) -> bool:
    """Install the CSS provider into Gtk default screen."""
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        gi.require_version("Gdk", "3.0")
        from gi.repository import Gtk, Gdk

        css_data = css(theme_name).encode("utf-8")
        provider = Gtk.CssProvider()
        provider.load_from_data(css_data)
        screen = Gdk.Screen.get_default()
        if screen:
            Gtk.StyleContext.add_provider_for_screen(
                screen,
                provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )
            return True
        return False
    except Exception as exc:
        logger.warning("Could not load GTK CSS: %s", exc)
        return False
