"""Unit tests for JARVIS GTK3 theme, orb colors, and UI bridge."""

import pytest
from jarvis.ui.theme import hex_to_rgba, PALETTE, ORB_STATES, css


def test_hex_to_rgba_valid():
    r, g, b, a = hex_to_rgba("#ffffff", 1.0)
    assert (r, g, b, a) == (1.0, 1.0, 1.0, 1.0)

    r, g, b, a = hex_to_rgba("#000000", 0.5)
    assert (r, g, b, a) == (0.0, 0.0, 0.0, 0.5)

    # Without leading hash
    r, g, b, a = hex_to_rgba("3fd0ff", 0.8)
    assert pytest.approx(r, 0.01) == 0.247
    assert pytest.approx(g, 0.01) == 0.815
    assert pytest.approx(b, 0.01) == 1.0
    assert a == 0.8


def test_hex_to_rgba_invalid():
    # Invalid lengths return black fallback
    r, g, b, a = hex_to_rgba("invalid", 1.0)
    assert (r, g, b, a) == (0.0, 0.0, 0.0, 1.0)


def test_orb_states_and_palette():
    required_states = ["idle", "listening", "thinking", "speaking", "working", "error"]
    for state in required_states:
        assert state in ORB_STATES
        assert ORB_STATES[state].startswith("#")

    assert "bg" in PALETTE
    assert "accent" in PALETTE
    assert "border" in PALETTE


def test_css_generation():
    gtk_css = css()
    assert isinstance(gtk_css, str)
    assert ".jarvis-surface" in gtk_css
    assert ".chat-user" in gtk_css
    assert ".chat-jarvis" in gtk_css
    assert ".floating-orb" in gtk_css
    assert ".orb-frame" in gtk_css


def test_orb_widget_headless():
    from jarvis.ui.orb import OrbWidget, GTK_AVAILABLE

    if not GTK_AVAILABLE:
        pytest.skip("GTK 3.0 not available on this platform.")

    widget = OrbWidget(size=120, state="idle")
    assert widget._size == 120
    assert widget._state == "idle"

    widget.set_state("thinking")
    assert widget._state == "thinking"
    assert widget._target_pulse > 0.1

    widget.set_label("TEST")
    assert widget._label == "TEST"

    widget.stop_animation()
    assert widget._animating is False


def test_cli_ui_flag_routing(monkeypatch):
    from unittest.mock import MagicMock
    import jarvis.cli.main as cli_main

    mock_launch = MagicMock(return_value=0)
    monkeypatch.setattr("jarvis.ui.app.launch_ui", mock_launch)

    # Run with explicit --ui flag
    res = cli_main.run_cli(["run", "--ui"])
    assert res == 0
    assert mock_launch.call_count == 1

    # Run with ui subcommand
    mock_launch.reset_mock()
    res = cli_main.run_cli(["ui"])
    assert res == 0
    assert mock_launch.call_count == 1
