"""
JARVIS UI theme — Cinnamon/Linux Mint friendly dark palette + CSS.

We keep GTK's own widget drawing (so it matches the Mint desktop) and only add a
cohesive JARVIS accent layer: deep space background, cyan/blue glow, and crisp text.
No heavy custom widgets — just colour + a little personality.
"""

# ── Palette (hex, no '#') ───────────────────────────────────────────────
PALETTE = {
    "bg":          "#0b0f1a",   # deep space (window background)
    "bg_panel":    "#111726",   # panel / card surface
    "bg_elev":     "#172033",   # elevated surface (hover, entries)
    "border":      "#26344f",   # hairline borders
    "text":        "#e8f0ff",   # primary text
    "text_dim":    "#8fa3c4",   # secondary text
    "accent":      "#3fd0ff",   # JARVIS cyan
    "accent2":     "#2f7bff",   # JARVIS blue
    "good":        "#39e0a0",   # idle / ok (green)
    "warn":        "#ffcf5c",   # thinking / caution (amber)
    "bad":         "#ff5c7a",   # error / blocked (red)
    "speaking":    "#7c9bff",   # speaking (periwinkle)
}

# Orb state → core colour
ORB_STATES = {
    "idle":      "#39e0a0",
    "listening": "#3fd0ff",
    "thinking":  "#ffcf5c",
    "speaking":  "#7c9bff",
    "working":   "#3fd0ff",
    "error":     "#ff5c7a",
}


def css() -> str:
    """Return the GTK CSS for the JARVIS UI as a string."""
    p = PALETTE
    return f"""
    /* ── JARVIS base ── */
    window, .background {{ background-color: {p['bg']}; }}
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
    label.accent {{ color: {p['accent']}; font-weight: 600; }}

    /* ── Orb HUD frame ── */
    .orb-frame {{
        background-color: {p['bg']};
        border-radius: 16px;
    }}

    /* ── Chat ── */
    .chat-scroll {{ background-color: {p['bg']}; }}
    .chat-user {{
        background-color: {p['accent2']};
        color: #ffffff;
        border-radius: 12px;
        padding: 8px 10px;
    }}
    .chat-jarvis {{
        background-color: {p['bg_elev']};
        color: {p['text']};
        border: 1px solid {p['border']};
        border-radius: 12px;
        padding: 8px 10px;
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
        padding: 6px 8px;
    }}
    entry:focus {{ border: 1px solid {p['accent']}; }}

    /* ── Buttons ── */
    button {{
        background-color: {p['bg_elev']};
        color: {p['text']};
        border: 1px solid {p['border']};
        border-radius: 8px;
        padding: 6px 12px;
    }}
    button:hover {{ background-color: #1d2b44; border: 1px solid {p['accent']}; }}
    button.suggested-action {{
        background-color: {p['accent2']};
        color: #ffffff;
        border: none;
    }}
    button.suggested-action:hover {{ background-color: #3f8cff; }}

    /* ── Stats / progress ── */
    progressbar trough {{ background-color: {p['bg_elev']}; border-radius: 6px; min-height: 8px; }}
    progressbar progress {{ background-color: {p['accent']}; border-radius: 6px; }}

    .floating-orb {{ background-color: transparent; }}
    """


def load_css(screen=None) -> None:
    """Install the JARVIS CSS into the default Gtk style provider."""
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gtk, Gdk
    css_data = css().encode("utf-8")
    provider = Gtk.CssProvider()
    provider.load_from_data(css_data)
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(),
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )
