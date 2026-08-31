# tests/test_voice_pipeline.py
import pytest, time, numpy as np
from voice.vad import VAD
from voice.wake_word import WakeWordDetector

def test_vad_low_threshold_detects_speech():
    v = VAD()
    # 0.01 RMS speech audio (typical float32 mic level)
    speech_audio = np.random.normal(0, 0.01, 480).astype(np.float32)
    v.calibrate(np.zeros(480, dtype=np.float32), multiplier=2.0)
    assert v.is_speech(speech_audio) is True

def test_wake_word_rms_prefilter_allows_normal_speech():
    d = WakeWordDetector()
    audio = np.random.normal(0, 0.005, 16000).astype(np.float32)
    is_wake, score = d.detect(audio)
    assert is_wake is False
