"""Tests for Auto Wake Word Service (Continuous Background Daemon & Ambient Voice)."""

import time
from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from jarvis.config.settings import Settings
from jarvis.voice.auto_wake import AutoWakeService
from jarvis.tools.builtin.voice_tools import toggle_auto_wake, configure_wake_word
from jarvis.cli.main import run_cli


def test_auto_wake_service_lifecycle():
    """Verify clean start, pause, resume, and stop lifecycle of AutoWakeService."""
    settings = Settings(auto_wake_word=True, wake_phrases="hey jarvis,jarvis")
    service = AutoWakeService(settings=settings)

    with patch.object(service, "_worker_loop", return_value=None):
        started = service.start()
        assert started
        assert service._running

        service.pause()
        assert service.is_paused

        service.resume()
        assert not service.is_paused

        service.stop()
        assert not service._running


def test_auto_wake_tools_execution():
    """Test toggle_auto_wake and configure_wake_word builtin tools."""
    # 1. Toggle auto wake
    res_enable = toggle_auto_wake(True)
    assert "ENABLED" in res_enable

    res_disable = toggle_auto_wake(False)
    assert "DISABLED" in res_disable

    # 2. Configure wake word
    res_cfg = configure_wake_word(phrases="computer,jarvis", ack_phrase="At your command.")
    assert "computer,jarvis" in res_cfg
    assert "At your command." in res_cfg


def test_auto_wake_detection_and_conversation():
    """Simulate wake-word detection followed by command capture and assistant reply."""
    settings = Settings(wake_phrases="hey jarvis", wake_ack_phrase="Yes, sir?", wake_followup_timeout=0.1)
    
    events = []
    def mock_command(cmd: str) -> str:
        events.append(("command", cmd))
        return "All systems operational, sir."

    service = AutoWakeService(
        on_command=mock_command,
        on_wake_detected=lambda p: events.append(("wake", p)),
        on_orb_state=lambda s: events.append(("orb", s)),
        on_chat=lambda r, t: events.append(("chat", r, t)),
        settings=settings,
    )

    # Mock components: detector returning True, mic recording speech, STT returning transcript
    mock_detector = MagicMock()
    mock_detector.feed.side_effect = [True, False]

    fake_speech_pcm = np.ones(3200, dtype="i2") * 1000

    mock_mic = MagicMock()
    mock_mic.iter_chunks.return_value = [fake_speech_pcm]
    mock_mic.record_until_silence.side_effect = [fake_speech_pcm, np.array([], dtype="i2")]

    mock_session = MagicMock()
    mock_session.speak_and_listen_duplex.return_value = None  # No barge-in

    with patch("jarvis.voice.auto_wake.WakeWordDetector", return_value=mock_detector), \
         patch("jarvis.voice.auto_wake.Microphone", return_value=mock_mic), \
         patch("jarvis.voice.auto_wake.DuplexVoiceSession", return_value=mock_session), \
         patch("jarvis.voice.auto_wake.transcribe_pcm", return_value="report system status"), \
         patch("jarvis.voice.auto_wake.speak") as mock_speak:

        # Run one worker cycle
        service._detector = mock_detector
        service._mic = mock_mic
        service._session = mock_session
        service._running = True

        service._handle_active_conversation()

        # Check acknowledgment speech
        mock_speak.assert_called_once_with("Yes, sir?", voice=settings.voice)

        # Verify event stream
        assert ("chat", "user", "report system status") in events
        assert ("chat", "assistant", "All systems operational, sir.") in events
        assert ("command", "report system status") in events


def test_cli_auto_wake_status(capsys):
    """Test CLI subcommand jarvis voice auto-wake-status."""
    ret = run_cli(["voice", "auto-wake-status"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "JARVIS Ambient Wake-Word Configuration & Status" in out
    assert "Trigger Phrases" in out
    assert "Silence Energy Gate" in out
