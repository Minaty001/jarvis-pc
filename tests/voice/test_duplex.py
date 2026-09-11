"""Tests for Full-Duplex Audio & Barge-in Interruption subsystem."""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from jarvis.voice.duplex import (
    BARGE_IN_WAKE_WORDS,
    BargeInDetector,
    DuplexVoiceSession,
    InterruptibleSpeaker,
)


def test_interruptible_speaker_normal_playback():
    speaker = InterruptibleSpeaker()
    pcm = (np.sin(np.linspace(0, 10, 4800)) * 10000).astype(np.int16)

    levels: list[float] = []

    def on_level(lvl: float):
        levels.append(lvl)

    # Mock sounddevice.OutputStream to avoid hardware requirements in tests
    with patch("sounddevice.OutputStream") as mock_stream_cls:
        mock_stream = MagicMock()
        mock_stream_cls.return_value.__enter__.return_value = mock_stream

        completed = speaker.play(pcm, sample_rate=24000, level_callback=on_level)

        assert completed is True
        assert not speaker.is_playing
        assert mock_stream.write.called
        assert len(levels) > 0


def test_interruptible_speaker_immediate_interruption():
    speaker = InterruptibleSpeaker()
    pcm = np.zeros(24000, dtype=np.int16)

    interrupt_event = threading.Event()

    with patch("sounddevice.OutputStream") as mock_stream_cls:
        mock_stream = MagicMock()

        def write_side_effect(chunk):
            # Simulate interruption during playback
            interrupt_event.set()

        mock_stream.write.side_effect = write_side_effect
        mock_stream_cls.return_value.__enter__.return_value = mock_stream

        completed = speaker.play(pcm, sample_rate=24000, interrupt_event=interrupt_event)

        assert completed is False
        assert mock_stream.abort.called


def test_barge_in_detector_vad_trigger():
    detector = BargeInDetector(mode="vad_only", sensitivity=1.5)

    # Quiet chunk should NOT trigger barge-in
    quiet_chunk = np.zeros(1280, dtype=np.int16)
    assert detector.is_barge_in(quiet_chunk, is_speaking=True) is False

    # Loud speech-like chunk should trigger elevated VAD barge-in
    loud_chunk = (np.sin(np.linspace(0, 50, 1280)) * 15000).astype(np.int16)
    assert detector.is_barge_in(loud_chunk, is_speaking=True) is True

    # Not speaking -> should not trigger barge-in
    assert detector.is_barge_in(loud_chunk, is_speaking=False) is False


def test_barge_in_detector_wake_word_trigger():
    detector = BargeInDetector(mode="wake_only")
    detector.detector = MagicMock()
    detector.detector.feed.return_value = True

    chunk = np.zeros(1280, dtype=np.int16)
    assert detector.is_barge_in(chunk, is_speaking=True) is True
    detector.detector.feed.assert_called_once()


def test_duplex_voice_session_speak_and_interrupt():
    session = DuplexVoiceSession()

    mock_pcm = (np.sin(np.linspace(0, 10, 4800)) * 5000).astype(np.int16)

    with patch("jarvis.voice.duplex.synthesize", return_value=b"fake_mp3"), \
         patch("jarvis.voice.duplex.decode_mp3", return_value=(mock_pcm, 24000, 1)), \
         patch.object(session.mic, "iter_chunks") as mock_iter_chunks:

        # Simulate user speaking a loud interruption during playback
        interruption_chunk = (np.sin(np.linspace(0, 50, 1280)) * 18000).astype(np.int16)
        mock_iter_chunks.return_value = [interruption_chunk]

        with patch.object(session.speaker, "play") as mock_play:
            def play_side_effect(pcm, **kwargs):
                # Wait briefly then return False (interrupted)
                time.sleep(0.05)
                return False

            mock_play.side_effect = play_side_effect
            interrupted_data = session.speak_and_listen_duplex("Test message")

            assert interrupted_data is not None
            assert len(interrupted_data) > 0


def test_duplex_voice_session_clean_completion():
    session = DuplexVoiceSession()
    mock_pcm = np.zeros(2400, dtype=np.int16)

    with patch("jarvis.voice.duplex.synthesize", return_value=b"fake_mp3"), \
         patch("jarvis.voice.duplex.decode_mp3", return_value=(mock_pcm, 24000, 1)), \
         patch.object(session.mic, "iter_chunks", return_value=[]), \
         patch.object(session.speaker, "play", return_value=True):

        res = session.speak_and_listen_duplex("Clean speech test")
        assert res is None
