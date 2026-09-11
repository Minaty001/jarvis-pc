"""JARVIS UI theme — Linux Mint / Cinnamon friendly dark palette and GTK CSS."""

from __future__ import annotations

import logging
from typing import Tuple

logger = logging.getLogger(__name__)

PALETTE = {
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
}

ORB_STATES = {
    "idle": "#39e0a0",
    "listening": "#3fd0ff",
    "thinking": "#ffcf5c",
    "speaking": "#7c9bff",
    "working": "#3fd0ff",
    "error": "#ff5c7a",
}


def hex_to_rgba(hex_str: str, alpha: float = 1.0) -> Tuple[float, float, float, float]:
    """Convert hex string (e.g. #3fd0ff or 3fd0ff) to (r, g, b, a) float tuple in [0.0, 1.0]."""
    h = hex_str.lstrip("#")
    if len(h) != 6:
        return (0.0, 0.0, 0.0, alpha)
    r = int(h[0:2], 16) / 255.0
    g = int(h[2:4], 16) / 255.0
    b = int(h[4:6], 16) / 255.0
    return (r, g, b, alpha)


def css() -> str:
    """Return GTK CSS styling string."""
    p = PALETTE
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


def load_css() -> bool:
    """Install the CSS provider into Gtk default screen."""
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        gi.require_version("Gdk", "3.0")
        from gi.repository import Gtk, Gdk

        css_data = css().encode("utf-8")
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
