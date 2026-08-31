"""
Voice Pipeline — Orchestrates the full voice interaction loop.
Mic → VAD → Wake Word → STT → Brain → TTS

Optimisations applied:
- Wake buffer uses collections.deque(maxlen) — O(1) append, no pop(0)
- Brain result runs on the shared TTS loop (no new event loop per command)
- Post-TTS mute managed solely by _speak_with_mute; no premature pre-set
- VAD calibration now enforces minimum threshold (in vad.py)
"""

import asyncio
import time
import threading
from collections import deque
from typing import Any, Optional

import numpy as np

from config.logger import get_logger
from config.settings import settings
from voice.microphone import microphone
from voice.vad import vad
from voice.wake_word import wake_word_detector
from voice.stt import whisper_stt
from voice.tts import edge_tts_engine

logger = get_logger("voice.pipeline")

# Whisper silence/noise hallucination blacklist
_HALLUCINATIONS = frozenset({
    "thank you.", "thank you", "subtitles by", "subtitles", "you",
    "bye", "bye.", "thank you for watching", "thanks for watching",
    "subscribe", "chuckles", "sighs", "laughter", "...", ". . .",
})


class VoicePipeline:
    """Full voice interaction pipeline."""

    _WAKE_BUF_CHUNKS = 34   # ~1 s at 30 ms/chunk
    _MAX_SILENCE     = 30   # 30 × 30 ms = 900 ms → end command
    _MAX_WAKE_SIL    = 100  # 100 × 30 ms = 3 s → timeout

    def __init__(self, brain: Any = None):
        self.brain = brain
        self._running = False
        self._listening_for_command = False
        # O(1) append/discard; automatically caps at maxlen
        self._wake_audio_buffer: deque[np.ndarray] = deque(maxlen=self._WAKE_BUF_CHUNKS)
        self._command_audio_buffer: list[np.ndarray] = []
        self._thread: Optional[threading.Thread] = None
        self._tts_loop: Optional[asyncio.AbstractEventLoop] = None
        self._tts_thread: Optional[threading.Thread] = None
        self._last_wake_time: float = 0.0
        self._wake_cooldown: float = 5.0  # seconds
        self._tts_playing: bool = False
        self._tts_lock: threading.Lock = threading.Lock()
        self._command_speech_chunks: int = 0
        self._post_tts_until: float = 0.0

    # ── Lifecycle ────────────────────────────────────────────────────────

    def _start_tts_loop(self) -> None:
        """Start a dedicated event loop for TTS in a background thread."""
        self._tts_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._tts_loop)
        self._tts_loop.run_forever()

    async def start(self) -> None:
        """Initialize and start the voice pipeline."""
        logger.info("Initializing voice pipeline...")

        # Load models
        wake_word_detector.load()
        whisper_stt.load()

        # Start microphone
        microphone.start()

        # Calibrate VAD with 1 s of ambient noise
        logger.info("Calibrating VAD with ambient noise...")
        ambient = microphone.read_blocking(duration_sec=1.0)
        if ambient is not None:
            vad.calibrate(ambient, multiplier=2.5)

        # Start TTS event loop in background thread
        self._tts_thread = threading.Thread(target=self._start_tts_loop, daemon=True)
        self._tts_thread.start()
        # Give the loop a moment to start
        time.sleep(0.05)

        # Start pipeline loop
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Voice pipeline started")

    # ── Main loop ────────────────────────────────────────────────────────

    def _run_loop(self) -> None:
        """Main voice pipeline loop (runs in dedicated thread)."""
        silence_chunks = 0
        wake_silence_chunks = 0

        while self._running:
            chunk = microphone.read(timeout=0.1)
            if chunk is None:
                continue

            now = time.time()

            # Mute mic while TTS is playing or in post-TTS grace period
            with self._tts_lock:
                tts_active = self._tts_playing
            if tts_active or now < self._post_tts_until:
                self._wake_audio_buffer.clear()
                self._command_audio_buffer.clear()
                self._listening_for_command = False
                continue

            if not self._listening_for_command:
                # ── Phase 1: Listen for wake word ──────────────────────
                if now - self._last_wake_time < self._wake_cooldown:
                    continue

                self._wake_audio_buffer.append(chunk)

                if len(self._wake_audio_buffer) >= self._WAKE_BUF_CHUNKS:
                    audio = np.concatenate(list(self._wake_audio_buffer))
                    self._wake_audio_buffer.clear()
                    is_wake, score = wake_word_detector.detect(audio)

                    if is_wake:
                        logger.info("Wake word detected! (score=%.3f)", score)
                        self._listening_for_command = True
                        self._command_audio_buffer = []
                        self._command_speech_chunks = 0
                        silence_chunks = 0
                        wake_silence_chunks = 0
            else:
                # ── Phase 2: Collect command audio ─────────────────────
                self._command_audio_buffer.append(chunk)

                if vad.is_speech(chunk):
                    silence_chunks = 0
                    self._command_speech_chunks += 1
                else:
                    silence_chunks += 1
                    wake_silence_chunks += 1

                # End command on trailing silence (min 5 speech chunks heard)
                if silence_chunks >= self._MAX_SILENCE and self._command_speech_chunks > 5:
                    self._process_command()
                    self._listening_for_command = False
                    self._command_audio_buffer.clear()
                    self._last_wake_time = time.time()
                    silence_chunks = 0
                    self._command_speech_chunks = 0

                # Timeout: no speech detected after wake word
                elif wake_silence_chunks >= self._MAX_WAKE_SIL and self._command_speech_chunks == 0:
                    logger.info("No speech after wake word, going back to listening")
                    self._listening_for_command = False
                    self._command_audio_buffer.clear()
                    self._last_wake_time = time.time()
                    silence_chunks = 0
                    wake_silence_chunks = 0

    # ── TTS ──────────────────────────────────────────────────────────────

    def _speak_async(self, text: str) -> None:
        """Schedule TTS on the dedicated event loop (non-blocking)."""
        loop = self._tts_loop
        if loop and loop.is_running() and not loop.is_closed():
            with self._tts_lock:
                self._tts_playing = True
            try:
                asyncio.run_coroutine_threadsafe(self._speak_with_mute(text), loop)
            except RuntimeError:
                with self._tts_lock:
                    self._tts_playing = False

    async def _speak_with_mute(self, text: str) -> None:
        """Speak text and manage mic mute state including post-TTS grace period."""
        try:
            await edge_tts_engine.speak(text)
        except Exception as e:
            logger.warning("TTS error: %s", e)
        finally:
            with self._tts_lock:
                self._tts_playing = False
            # Post-TTS mute: 1.5 s to absorb speaker echo
            self._post_tts_until = time.time() + 1.5

    # ── Command processing ────────────────────────────────────────────────

    def _process_command(self) -> None:
        """Transcribe and dispatch the buffered command audio."""
        if not self._command_audio_buffer:
            return

        audio = np.concatenate(self._command_audio_buffer)
        duration = len(audio) / settings.sample_rate
        logger.info("Processing command audio (%.1fs)", duration)

        text = whisper_stt.transcribe(audio)
        if not text:
            logger.info("No speech detected in command")
            return

        # Filter hallucinations and garbage
        clean = text.strip().lower()
        if not clean or clean in _HALLUCINATIONS or len(clean) < 2:
            logger.info("Ignored hallucinated speech: '%s'", text)
            return

        logger.info("Command: '%s'", text)

        if self.brain:
            # Reuse the TTS loop instead of creating a new event loop per call
            async def _run_brain():
                try:
                    result = await self.brain.process_utterance(text)
                    response_text = ""
                    if isinstance(result, dict):
                        response_text = result.get("response_text", "")
                        if not response_text:
                            results = result.get("result", {}).get("results", [])
                            if isinstance(results, list) and results:
                                last = results[-1]
                                if isinstance(last, dict):
                                    response_text = last.get("result", "")
                        if not response_text:
                            response_text = str(result.get("result", ""))
                    if response_text and response_text.strip():
                        await self._speak_with_mute(response_text.strip())
                except Exception as exc:
                    logger.error("Brain processing error: %s", exc)

            loop = self._tts_loop
            if loop and loop.is_running():
                with self._tts_lock:
                    self._tts_playing = True
                asyncio.run_coroutine_threadsafe(_run_brain(), loop)

    # ── Shutdown ──────────────────────────────────────────────────────────

    def stop(self) -> None:
        """Stop the voice pipeline gracefully."""
        self._running = False
        microphone.stop()
        if self._thread:
            self._thread.join(timeout=3.0)
        if self._tts_loop and self._tts_loop.is_running():
            self._tts_loop.call_soon_threadsafe(self._tts_loop.stop)
        if self._tts_thread:
            self._tts_thread.join(timeout=2.0)
        logger.info("Voice pipeline stopped")
