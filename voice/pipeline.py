"""
Voice Pipeline — Orchestrates the full voice interaction loop.
Mic → VAD → Wake Word → STT → Brain → TTS
"""

import asyncio
import time
import threading
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


class VoicePipeline:
    """Full voice interaction pipeline."""

    def __init__(self, brain: Any = None):
        self.brain = brain
        self._running = False
        self._listening_for_command = False
        self._wake_audio_buffer: list[np.ndarray] = []
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

        # Calibrate VAD with ambient noise
        logger.info("Calibrating VAD with ambient noise...")
        ambient = microphone.read_blocking(duration_sec=1.0)
        if ambient is not None:
            vad.calibrate(ambient, multiplier=2.5)

        # Start TTS event loop in background thread
        self._tts_thread = threading.Thread(target=self._start_tts_loop, daemon=True)
        self._tts_thread.start()

        # Start pipeline loop
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Voice pipeline started")

    def _run_loop(self) -> None:
        """Main voice pipeline loop (runs in thread)."""
        silence_chunks = 0
        max_silence = 30  # 30 * 30ms = 900ms silence to end command
        wake_silence_chunks = 0
        max_wake_silence = 100  # 100 * 30ms = 3s max wait for speech after wake

        while self._running:
            chunk = microphone.read(timeout=0.1)
            if chunk is None:
                continue

            now = time.time()

            # Mute mic and skip audio while TTS is playing or in post-TTS grace period
            with self._tts_lock:
                tts_active = self._tts_playing
            if tts_active or now < self._post_tts_until:
                self._wake_audio_buffer.clear()
                self._command_audio_buffer.clear()
                self._listening_for_command = False
                continue

            if not self._listening_for_command:
                # Phase 1: Listen for wake word
                if now - self._last_wake_time < self._wake_cooldown:
                    continue

                self._wake_audio_buffer.append(chunk)
                if len(self._wake_audio_buffer) > 34:  # ~1 second buffer
                    self._wake_audio_buffer.pop(0)

                if len(self._wake_audio_buffer) >= 34:
                    audio = np.concatenate(self._wake_audio_buffer)
                    is_wake, score = wake_word_detector.detect(audio)
                    self._wake_audio_buffer.clear()

                    if is_wake:
                        logger.info("Wake word detected! (score=%.3f)", score)
                        self._listening_for_command = True
                        self._command_audio_buffer = []
                        self._command_speech_chunks = 0
                        silence_chunks = 0
                        wake_silence_chunks = 0
            else:
                # Phase 2: Collect command audio
                self._command_audio_buffer.append(chunk)

                if vad.is_speech(chunk):
                    silence_chunks = 0
                    self._command_speech_chunks += 1
                else:
                    silence_chunks += 1
                    wake_silence_chunks += 1

                # End command on silence (only if we heard some speech)
                if silence_chunks >= max_silence and self._command_speech_chunks > 5:
                    self._process_command()
                    self._listening_for_command = False
                    self._command_audio_buffer.clear()
                    self._last_wake_time = time.time()
                    self._post_tts_until = time.time() + 1.0
                    silence_chunks = 0
                    self._command_speech_chunks = 0

                # Timeout: no speech at all after wake word
                elif wake_silence_chunks >= max_wake_silence and self._command_speech_chunks == 0:
                    logger.info("No speech after wake word, going back to listening")
                    self._listening_for_command = False
                    self._command_audio_buffer.clear()
                    self._last_wake_time = time.time()
                    silence_chunks = 0
                    wake_silence_chunks = 0

    def _speak_async(self, text: str) -> None:
        """Speak text asynchronously via the TTS event loop, muting mic during playback."""
        if self._tts_loop and self._tts_loop.is_running() and not self._tts_loop.is_closed():
            with self._tts_lock:
                self._tts_playing = True
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self._speak_with_mute(text),
                    self._tts_loop,
                )
            except RuntimeError:
                with self._tts_lock:
                    self._tts_playing = False

    async def _speak_with_mute(self, text: str) -> None:
        """Speak text and manage mic mute state."""
        try:
            await edge_tts_engine.speak(text)
        except Exception as e:
            logger.warning("TTS error: %s", e)
        finally:
            with self._tts_lock:
                self._tts_playing = False
                self._post_tts_until = time.time() + 1.0

    def _process_command(self) -> None:
        """Process the collected command audio."""
        if not self._command_audio_buffer:
            return

        audio = np.concatenate(self._command_audio_buffer)
        duration = len(audio) / settings.sample_rate
        logger.info("Processing command audio (%.1fs)", duration)

        # Transcribe
        text = whisper_stt.transcribe(audio)
        if not text:
            logger.info("No speech detected in command")
            return

        # Filter known Whisper silence / noise hallucinations
        hallucinations = {
            "thank you.", "thank you", "subtitles by", "subtitles", "you",
            "bye", "bye.", "thank you for watching", "thanks for watching",
            "subscribe", "chuckles", "sighs", "laughter"
        }
        clean_text = text.strip().lower()
        if not clean_text or clean_text in hallucinations or len(clean_text) < 2:
            logger.info("Ignored empty or hallucinated speech: '%s'", text)
            return

        logger.info("Command: '%s'", text)

        # Process with brain
        if self.brain:
            try:
                loop = asyncio.new_event_loop()
                result = loop.run_until_complete(
                    self.brain.process_utterance(text)
                )
                loop.close()

                # Extract response text from brain result
                response_text = ""
                if isinstance(result, dict):
                    response_text = result.get("response_text", "")
                    if not response_text and "results" in result:
                        results = result["results"]
                        if isinstance(results, list) and len(results) > 0:
                            first = results[0]
                            if isinstance(first, dict):
                                response_text = first.get("response_text", first.get("result", ""))
                    if not response_text:
                        response_text = result.get("result", "")
                
                if response_text:
                    self._speak_async(response_text)
            except Exception as e:
                logger.error("Brain processing error: %s", e)

    def stop(self) -> None:
        """Stop the voice pipeline."""
        self._running = False
        microphone.stop()
        if self._thread:
            self._thread.join(timeout=3.0)
        
        # Stop TTS event loop
        if self._tts_loop and self._tts_loop.is_running():
            self._tts_loop.call_soon_threadsafe(self._tts_loop.stop)
        if self._tts_thread:
            self._tts_thread.join(timeout=2.0)
        
        logger.info("Voice pipeline stopped")
