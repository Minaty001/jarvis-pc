import time
import numpy as np
import pytest
from jarvis.wake_word import WakeWordDetector
from jarvis.audio_device import detect_and_configure_bluetooth_mic, get_active_microphone_name


def test_audio_device_detection():
    is_bt, desc = detect_and_configure_bluetooth_mic()
    assert isinstance(is_bt, bool)
    assert isinstance(desc, str)
    active_name = get_active_microphone_name()
    assert isinstance(active_name, str)


def test_detector_initialization():
    detector = WakeWordDetector(wake_words=["hey_jarvis"], auto_start=False)
    assert not detector.is_running
    assert "hey_jarvis" in detector.wake_words


def test_detector_audio_chunk_inference():
    detected_events = []

    def on_detect(name: str, score: float):
        detected_events.append((name, score))

    detector = WakeWordDetector(
        wake_words=["hey_jarvis"],
        threshold=0.5,
        on_wake_word=on_detect,
        auto_start=False,
    )
    detector._running = True

    # Pass silent dummy chunk (1280 int16 samples)
    dummy_chunk = np.zeros(1280, dtype=np.int16).tobytes()
    detector._audio_callback(dummy_chunk, 1280, None, None)

    # Silent audio should not trigger detection
    assert len(detected_events) == 0

    # Test explicit handle detection
    detector._handle_detection("hey_jarvis", 0.95)
    assert len(detected_events) == 1
    assert detected_events[0][0] == "hey_jarvis"
    assert pytest.approx(detected_events[0][1], 0.01) == 0.95
