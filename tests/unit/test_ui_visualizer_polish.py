"""Unit tests for UI visualizer polish, theme manager, and particle rendering."""

from __future__ import annotations

import math
import pytest

from jarvis.ui.theme import THEMES, ThemeManager, css, get_theme_manager, hex_to_rgba
from jarvis.ui.orb import OrbParticle, OrbWidget
from jarvis.ui.waveform import WaveformWidget


def test_theme_manager_presets():
    tm = ThemeManager()
    themes = tm.list_themes()
    assert "arc_reactor" in themes
    assert "stark_gold" in themes
    assert "cyberpunk" in themes
    assert "quantum_emerald" in themes

    assert tm.set_theme("stark_gold") is True
    assert tm.active_theme == "stark_gold"
    pal = tm.get_palette()
    assert pal["bg"] == THEMES["stark_gold"]["palette"]["bg"]

    states = tm.get_orb_states()
    assert "listening" in states

    # Reset back to default
    assert tm.set_theme("arc_reactor") is True


def test_theme_css_generation():
    for t_key in THEMES:
        style_css = css(t_key)
        assert "window" in style_css
        assert ".jarvis-surface" in style_css
        assert THEMES[t_key]["palette"]["bg"] in style_css


def test_orb_particle_physics():
    p = OrbParticle(index=0, total=10)
    initial_angle = p.angle
    p.step(pulse_mult=0.5)
    assert p.angle != initial_angle


def test_orb_widget_headless_tick():
    try:
        orb = OrbWidget(size=200, state="idle")
        assert len(orb._particles) == 32
        orb.set_state("listening")
        assert orb._state == "listening"
        assert orb._target_pulse > 0.1

        # Simulate animation step
        assert orb._tick_anim() is True
        assert orb._tick > 0
        orb.stop_animation()
    except RuntimeError:
        pytest.skip("GTK / Cairo not available in headless environment")


def test_waveform_widget_headless_tick():
    try:
        wf = WaveformWidget(width=240, height=50, state="idle")
        assert wf._num_bars == 16
        wf.feed_level(0.8)
        assert wf._target_level == 0.8

        # Simulate animation step
        assert wf._tick_anim() is True
        assert wf._level > 0.05
        assert len(wf._bars) == 16
        wf.stop_animation()
    except RuntimeError:
        pytest.skip("GTK / Cairo not available in headless environment")
