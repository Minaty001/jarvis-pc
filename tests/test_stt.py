import numpy as np
import pytest
from jarvis.stt import StreamTranscriber, get_stt_model


def test_stt_model_loading():
    model = get_stt_model()
    assert model is not None


def test_transcriber_lifecycle():
    transcriber = StreamTranscriber(sample_rate=16000)
    transcriber.start()
    assert transcriber.rec is not None
    assert transcriber._speech_started is False

    # Feeding silent chunk
    dummy_chunk = np.zeros(1280, dtype=np.int16)
    is_complete, partial, full = transcriber.process_chunk(dummy_chunk)
    assert is_complete is False
    assert partial == ""
    assert full == ""

    # Finalize should return clean text and be idempotent
    final_1 = transcriber.finalize()
    final_2 = transcriber.finalize()
    assert final_1 == ""
    assert final_2 == ""


def test_transcriber_no_speech_timeout():
    transcriber = StreamTranscriber(sample_rate=16000, no_speech_timeout=0.2)
    transcriber.start()

    # Artificially set start_time back
    transcriber._start_time -= 0.5

    dummy_chunk = np.zeros(1280, dtype=np.int16)
    is_complete, partial, full = transcriber.process_chunk(dummy_chunk)
    assert is_complete is True
    assert full == ""
