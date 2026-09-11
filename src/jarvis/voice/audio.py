"""Shared audio helpers: decode MP3, resample to 16k mono, wrap PCM in WAV."""

import io
import wave

import numpy as np


def decode_mp3(data: bytes):
    """Decode MP3 bytes to (int16 PCM ndarray [n, ch], sample_rate, channels)."""
    import miniaudio

    dec = miniaudio.decode(data, output_format=miniaudio.SampleFormat.SIGNED16)
    pcm = np.frombuffer(dec.samples, dtype="<i2").reshape(-1, dec.nchannels)
    return pcm, dec.sample_rate, dec.nchannels


def to_mono(pcm: np.ndarray) -> np.ndarray:
    """Average multi-channel int16 PCM down to mono (ravel if already mono)."""
    if pcm.ndim == 2 and pcm.shape[1] > 1:
        return pcm.mean(axis=1).astype("<i2")
    return pcm.ravel()


def resample_16k(pcm: np.ndarray, sample_rate: int) -> np.ndarray:
    """Linear resample int16 mono PCM to 16 kHz mono."""
    if sample_rate == 16000:
        return pcm.astype("<i2")
    n = int(len(pcm) / sample_rate * 16000)
    x_in = np.linspace(0.0, 1.0, len(pcm))
    x_out = np.linspace(0.0, 1.0, n)
    return np.interp(x_out, x_in, pcm.astype("f8")).astype("<i2")


def pcm_to_wav_bytes(pcm: np.ndarray, sample_rate: int) -> bytes:
    """Wrap int16 PCM bytes in a WAV container (single channel)."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(np.ascontiguousarray(pcm, dtype="<i2").tobytes())
    return buf.getvalue()