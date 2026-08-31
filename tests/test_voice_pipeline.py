# tests/test_voice_pipeline.py
import pytest, time, numpy as np
from voice.vad import VAD
from voice.wake_word import WakeWordDetector

def test_vad_low_threshold_detects_speech():
    v = VAD()
    speech_audio = np.random.normal(0, 0.01, 480).astype(np.float32)
    v.calibrate(np.zeros(480, dtype=np.float32), multiplier=2.0)
    assert v.is_speech(speech_audio) is True

def test_openwakeword_onnx_load_and_detect():
    d = WakeWordDetector()
    loaded = d.load()
    assert loaded is True
    audio = np.random.normal(0, 0.005, 16000).astype(np.float32)
    is_wake, score = d.detect(audio)
    assert isinstance(is_wake, bool)
    assert isinstance(score, float)
