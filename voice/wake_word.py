"""
Wake Word Detection — 3-stage ONNX pipeline.
Stage 1: melspectrogram.onnx (PCM → Mel)
Stage 2: embedding_model.onnx (Mel → Embedding)
Stage 3: hey_jarvis.onnx (Embedding → Score)
"""

import threading
from pathlib import Path
from typing import Optional

import numpy as np

from config.logger import get_logger
from config.settings import settings

logger = get_logger("voice.wakeword")

try:
    import onnxruntime as ort
    HAS_ONNX = True
except ImportError:
    HAS_ONNX = False
    logger.warning("onnxruntime not installed. Wake word disabled.")


class WakeWordDetector:
    """3-stage ONNX wake word detector."""

    def __init__(self, threshold: float = None):
        self.threshold = threshold or settings.wake_threshold
        self._mel_session: Optional[ort.InferenceSession] = None
        self._embed_session: Optional[ort.InferenceSession] = None
        self._classify_session: Optional[ort.InferenceSession] = None
        self._loaded = False
        self._consecutive_errors = 0
        self._error_log_interval = 50  # Log every 50 consecutive errors

    def load(self) -> bool:
        """Load all three ONNX models."""
        if not HAS_ONNX:
            return False

        wakeword_dir = settings.wakeword_dir
        mel_path = wakeword_dir / "melspectrogram.onnx"
        embed_path = wakeword_dir / "embedding_model.onnx"
        classify_path = wakeword_dir / "hey_jarvis.onnx"

        for p in [mel_path, embed_path, classify_path]:
            if not p.exists():
                logger.error("Wake word model not found: %s", p)
                return False

        try:
            opts = ort.SessionOptions()
            opts.inter_op_num_threads = 1
            opts.intra_op_num_threads = 2

            self._mel_session = ort.InferenceSession(str(mel_path), opts)
            self._embed_session = ort.InferenceSession(str(embed_path), opts)
            self._classify_session = ort.InferenceSession(str(classify_path), opts)
            self._loaded = True
            logger.info("Wake word models loaded from %s", wakeword_dir)
            return True
        except Exception as e:
            logger.error("Failed to load wake word models: %s", e)
            return False

    def _compute_mel(self, audio: np.ndarray) -> np.ndarray:
        """Stage 1: Compute mel spectrogram from PCM audio."""
        audio_float = audio.astype(np.float32)
        if audio_float.max() > 1.0:
            audio_float = audio_float / 32768.0

        input_name = self._mel_session.get_inputs()[0].name
        mel = self._mel_session.run(None, {input_name: audio_float[np.newaxis, :]})[0]
        # mel shape: (time, 1, freq, 32) -> squeeze to (time, freq, 32)
        # Find and squeeze the singleton dim
        for i in range(mel.ndim):
            if mel.shape[i] == 1:
                mel = mel.squeeze(i)
                break
        return mel

    def _compute_embedding(self, mel: np.ndarray) -> np.ndarray:
        """Stage 2: Compute stacked embeddings from mel spectrogram.

        The embedding model expects (batch, 76, 32, 1) and outputs (batch, 1, 1, 96).
        The classifier expects (1, 16, 96) -- 16 stacked embeddings.
        We slide a 76-frame window across the mel spectrogram to produce 16 embeddings.
        """
        nframes = mel.shape[1]
        window = 76
        num_embeddings = 16

        if nframes < window:
            pad_width = ((0, 0), (0, window - nframes), (0, 0))
            mel = np.pad(mel, pad_width, mode='constant')
            nframes = mel.shape[1]

        # Calculate stride to get exactly num_embeddings windows
        if nframes <= window:
            stride = 1
        else:
            stride = max(1, (nframes - window) // (num_embeddings - 1))

        embeddings = []
        for i in range(num_embeddings):
            start = i * stride
            chunk = mel[:, start:start + window, :]  # (1, 76, 32)
            chunk_4d = chunk[:, :, :, np.newaxis]     # (1, 76, 32, 1)
            input_name = self._embed_session.get_inputs()[0].name
            emb = self._embed_session.run(None, {input_name: chunk_4d})[0]
            embeddings.append(emb.reshape(1, 1, 96))
            if start + window >= nframes:
                break

        # Pad to exactly 16 embeddings if we got fewer
        while len(embeddings) < num_embeddings:
            embeddings.append(embeddings[-1].copy())

        # Stack to (1, 16, 96)
        return np.concatenate(embeddings[:num_embeddings], axis=1)

    def _classify(self, embedding: np.ndarray) -> float:
        """Stage 3: Classify embedding as wake word score."""
        input_name = self._classify_session.get_inputs()[0].name
        score = self._classify_session.run(None, {input_name: embedding})[0]
        return float(score[0][0]) if score.ndim > 0 else float(score[0])

    def detect(self, audio: np.ndarray) -> tuple[bool, float]:
        """
        Run full 3-stage detection pipeline.
        Returns (is_wake_word, confidence_score).

        Pre-check: skip ONNX inference entirely if audio energy is below
        the minimum speech floor (0.008 RMS for float32). This prevents
        the classifier from firing score=1.000 on near-silence buffers.
        """
        if not self._loaded:
            return False, 0.0

        # Fast pre-filter: don't run ONNX on silent audio
        rms = float(np.sqrt(np.mean(audio.astype(np.float32) ** 2)))
        if rms < 0.008:
            return False, 0.0

        try:
            mel = self._compute_mel(audio)
            embedding = self._compute_embedding(mel)
            score = self._classify(embedding)
            is_wake = score >= self.threshold
            self._consecutive_errors = 0  # Reset on success
            return is_wake, score
        except Exception as e:
            self._consecutive_errors += 1
            # Rate-limit error logging to prevent log spam
            if self._consecutive_errors % self._error_log_interval == 1:
                logger.warning("Wake word detection error (consecutive %d): %s",
                               self._consecutive_errors, e)
            return False, 0.0

    @property
    def is_loaded(self) -> bool:
        return self._loaded


wake_word_detector = WakeWordDetector()
