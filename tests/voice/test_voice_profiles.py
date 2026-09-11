"""Tests for Voice Personality & Multi-Language Profiles."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from jarvis.config.settings import Settings
from jarvis.voice.profiles import (
    VOICE_PROFILES,
    VoiceProfile,
    VoiceProfileManager,
    get_voice_profile,
    list_voice_profiles as list_profiles_func,
)
from jarvis.tools.builtin.voice_tools import (
    list_voice_profiles,
    set_voice_profile,
    tune_voice_acoustics,
)
from jarvis.cli.main import run_cli


def test_voice_profile_catalog():
    """Verify standard profiles exist in the catalog."""
    expected = [
        "british_butler",
        "classic_jarvis",
        "tactical_ai",
        "indian_english",
        "hindi_assistant",
        "french_ai",
        "german_ai",
    ]
    for key in expected:
        assert key in VOICE_PROFILES
        prof = VOICE_PROFILES[key]
        assert prof.key == key
        assert prof.voice
        assert prof.language
        assert prof.name


def test_voice_profile_manager_active_profile():
    """Test manager correctly identifies active profile and falls back gracefully."""
    settings = Settings(voice_profile="tactical_ai", voice="en-US-GuyNeural")
    mgr = VoiceProfileManager(settings=settings)
    active = mgr.get_active_profile()
    assert active.key == "tactical_ai"
    assert active.voice == "en-US-ChristopherNeural"
    assert active.pitch == "-4Hz"

    # Test unknown profile fallback
    prof = mgr.get_profile("non_existent_profile")
    assert prof.key == "british_butler"


def test_voice_profile_manager_set_profile():
    """Test switching profile updates settings and manager state."""
    settings = Settings()
    mgr = VoiceProfileManager(settings=settings)

    new_prof = mgr.set_profile("indian_english")
    assert new_prof.key == "indian_english"
    assert settings.voice_profile == "indian_english"
    assert settings.voice == "en-IN-PrabhatNeural"
    assert settings.voice_rate == "+0%"

    with pytest.raises(ValueError, match="Unknown voice profile"):
        mgr.set_profile("alien_voice_unknown")


def test_voice_profile_manager_tune_acoustics():
    """Test tuning rate and pitch."""
    settings = Settings()
    mgr = VoiceProfileManager(settings=settings)
    
    prof = mgr.tune_acoustics(rate="+15%", pitch="+5Hz")
    assert prof.rate == "+15%"
    assert prof.pitch == "+5Hz"
    assert settings.voice_rate == "+15%"
    assert settings.voice_pitch == "+5Hz"


def test_voice_tools_execution():
    """Test builtin tools: list_voice_profiles, set_voice_profile, tune_voice_acoustics."""
    # 1. list_voice_profiles
    res_list = list_voice_profiles()
    assert "british_butler" in res_list
    assert "classic_jarvis" in res_list
    assert "ACTIVE" in res_list

    # 2. set_voice_profile
    res_set = set_voice_profile("tactical_ai")
    assert "Tactical Combat AI" in res_set
    assert "en-US-ChristopherNeural" in res_set

    # 3. set invalid profile
    res_err = set_voice_profile("unknown_xxx")
    assert "Unknown voice profile" in res_err

    # 4. tune_voice_acoustics
    res_tune = tune_voice_acoustics(rate="+10%", pitch="-2Hz")
    assert "Acoustic tuning applied" in res_tune
    assert "+10%" in res_tune
    assert "-2Hz" in res_tune


@pytest.mark.asyncio
async def test_tts_synthesize_acoustics():
    """Test that tts.synthesize_async correctly passes rate and pitch to edge_tts."""
    from jarvis.voice import tts

    async def mock_stream():
        yield {"type": "audio", "data": b"chunk_1"}
        yield {"type": "audio", "data": b"chunk_2"}

    with patch("edge_tts.Communicate") as mock_class:
        mock_instance = MagicMock()
        mock_instance.stream = mock_stream
        mock_class.return_value = mock_instance

        data = await tts.synthesize_async("Hello world", voice="en-GB-RyanNeural", rate="+10%", pitch="-4Hz")
        assert data == b"chunk_1chunk_2"
        mock_class.assert_called_once_with(
            text="Hello world",
            voice="en-GB-RyanNeural",
            rate="+10%",
            pitch="-4Hz",
            volume="+0%",
        )


def test_cli_voice_subcommands(capsys):
    """Test CLI commands: jarvis voice profiles and jarvis voice set-profile."""
    # 1. profiles command
    ret = run_cli(["voice", "profiles"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "JARVIS Neural Voice Personality Profiles" in out
    assert "british_butler" in out
    assert "tactical_ai" in out

    # 2. set-profile command
    ret = run_cli(["voice", "set-profile", "tactical_ai"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "Successfully activated voice profile 'tactical_ai'" in out
