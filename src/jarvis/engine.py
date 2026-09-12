"""JARVIS Unified Single-Stream Voice Assistant & Task Execution Engine.

Operates on a continuous single audio stream state machine:
WAKE_WORD_LISTENING -> PROMPT_RESPONDING ('Yes boss') -> COMMAND_LISTENING -> EXECUTING_TASK -> WAKE_WORD_LISTENING
"""

from __future__ import annotations

from enum import Enum, auto
import logging
import os
import sys
import threading
import time
import warnings
from typing import Callable, List, Optional

# Suppress onnxruntime provider warnings
warnings.filterwarnings("ignore", category=UserWarning, module="onnxruntime")
os.environ["ORT_LOGGING_LEVEL"] = "3"

import numpy as np
import openwakeword
from openwakeword.model import Model
import sounddevice as sd

from .audio_device import detect_and_configure_bluetooth_mic, get_active_microphone_name
from .planner import ExecutionReport, TaskPlanner
from .stt import StreamTranscriber
from .voice import init_voice, speak_text, speak_yes_boss

logger = logging.getLogger("jarvis.engine")


class EngineState(Enum):
    WAKE_WORD_LISTENING = auto()
    PROMPT_RESPONDING = auto()
    COMMAND_LISTENING = auto()
    EXECUTING_TASK = auto()


class JarvisEngine:
    """Unified Single-Stream Voice Assistant & Task Engine."""

    def __init__(
        self,
        threshold: float = 0.30,
        model: str = "hey_jarvis",
        device: Optional[int | str] = None,
        auto_start: bool = False,
    ) -> None:
        self.threshold = threshold
        self.model_name = model
        self.device = device
        self.sample_rate = 16000
        self.chunk_size = 1280

        self.state = EngineState.WAKE_WORD_LISTENING
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_trigger_time: float = 0.0
        self._debounce_seconds: float = 1.5
        self._last_displayed_text: str = ""

        # Initialize components
        self.planner = TaskPlanner()
        self.transcriber = StreamTranscriber(sample_rate=self.sample_rate)
        init_voice()

        # Load openWakeWord models
        self.wakeword_model = self._load_wakeword_model()

        if auto_start:
            self.start()

    def _load_wakeword_model(self) -> Model:
        """Find and load specified openWakeWord models."""
        all_paths = openwakeword.get_pretrained_model_paths()
        selected_paths: List[str] = []

        for path in all_paths:
            if self.model_name.lower() in path.lower():
                selected_paths.append(path)
                break

        if selected_paths:
            logger.info("Loading wake word models: %s", selected_paths)
            return Model(wakeword_model_paths=selected_paths)

        logger.info("Loading all default openWakeWord models")
        return Model()

    def _audio_callback(self, in_data, frames, time_info, status) -> None:
        """Process incoming audio chunks from single continuous stream."""
        if status:
            logger.debug("Audio status: %s", status)

        if not self._running:
            return

        raw_chunk = np.frombuffer(in_data, dtype=np.int16)
        now = time.time()

        # --- STATE 1: WAKE WORD LISTENING ---
        if self.state == EngineState.WAKE_WORD_LISTENING:
            if hasattr(self, "_last_energy_log") and (now - self._last_energy_log) >= 5.0:
                self._last_energy_log = now
                rms = np.sqrt(np.mean(raw_chunk.astype(float) ** 2)) if len(raw_chunk) > 0 else 0
                logger.info("🎤 Listening for '%s' | Mic RMS: %.1f", self.model_name, rms)
            elif not hasattr(self, "_last_energy_log"):
                self._last_energy_log = now

            try:
                predictions = self.wakeword_model.predict(raw_chunk)
                for raw_name, score in predictions.items():
                    is_target = "jarvis" in raw_name.lower() or self.model_name.lower() in raw_name.lower()
                    if is_target:
                        if score >= self.threshold:
                            if (now - self._last_trigger_time) >= self._debounce_seconds:
                                self._last_trigger_time = now
                                self._on_wake_word_detected(raw_name, float(score))
                                break
                        elif score >= 0.15:
                            logger.debug("Partial wake word score '%s': %.3f", raw_name, score)
            except Exception as err:
                logger.error("Error in wake word inference: %s", err)

        # --- STATE 3: COMMAND LISTENING ---
        elif self.state == EngineState.COMMAND_LISTENING:
            is_complete, partial_text, current_full = self.transcriber.process_chunk(raw_chunk)
            
            # Display real-time streaming recognition in console
            display_text = current_full or partial_text
            if display_text and display_text != self._last_displayed_text:
                self._last_displayed_text = display_text
                print(f"\r🎙️ Hearing: \"{display_text}\" ...", end="", flush=True)

            if is_complete:
                print()  # newline after live streaming text
                final_command = current_full or self.transcriber.finalize()
                self._on_command_captured(final_command)

    def _on_wake_word_detected(self, name: str, score: float) -> None:
        """Triggered upon detecting the wake word."""
        self.state = EngineState.PROMPT_RESPONDING
        clean_name = name.replace("_v0.1", "")
        print("\n" + "=" * 50)
        print(f"🔥 [JARVIS EVENT] Wake word '{clean_name}' DETECTED! (Score: {score:.2f})")
        print("🔊 JARVIS: Yes boss")
        print("=" * 50 + "\n", flush=True)

        def _transition_to_command():
            # Play 'Yes boss' synchronously to completion so playback doesn't leak into mic
            speak_yes_boss(block=True)
            time.sleep(0.1)  # small settle delay
            self._last_displayed_text = ""
            print("🎙️ JARVIS is listening for your command...", flush=True)
            self.transcriber.start()
            self.state = EngineState.COMMAND_LISTENING

        threading.Thread(target=_transition_to_command, daemon=True, name="PromptTransition").start()

    def _on_command_captured(self, command: str) -> None:
        """Handle captured speech command and execute tasks."""
        self.state = EngineState.EXECUTING_TASK

        def _execute_worker():
            clean_cmd = command.strip()
            if not clean_cmd:
                print("⏳ No command heard. Returning to wake word listening...\n", flush=True)
            else:
                print(f"\n⚡ Processing command: \"{clean_cmd}\"")
                report = self.planner.process(clean_cmd)

                print("\n" + "-" * 50)
                print(f"📋 Tasks Executed: {len(report.results)}")
                for idx, res in enumerate(report.results, 1):
                    icon = "✅" if res.success else "❌"
                    print(f"  {idx}. {icon} {res.message}")
                print("-" * 50)

                if report.summary_message:
                    print(f"🔊 JARVIS: {report.summary_message}\n", flush=True)
                    speak_text(report.summary_message, block=True)

            # Settle time after TTS, reset openWakeWord buffers, and return to wake word state
            time.sleep(0.3)
            try:
                self.wakeword_model.reset()
            except Exception:
                pass
            self._last_trigger_time = time.time()
            self.state = EngineState.WAKE_WORD_LISTENING
            logger.info("🔄 Returned to wake word listening state.")

        threading.Thread(target=_execute_worker, daemon=True, name="TaskExecutionThread").start()

    def process_text_command(self, text: str) -> ExecutionReport:
        """Directly process a written/text command."""
        return self.planner.process(text)

    def _listen_loop(self) -> None:
        """Main continuous single audio stream loop."""
        logger.info("Unified audio stream active (16kHz, 1280 chunk)...")
        try:
            with sd.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=self.chunk_size,
                channels=1,
                dtype="int16",
                device=self.device,
                callback=self._audio_callback,
            ):
                while self._running:
                    time.sleep(0.05)
        except Exception as err:
            logger.error("Audio stream error: %s", err)
            self._running = False

    def start(self) -> None:
        """Start unified audio stream in background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True, name="UnifiedAudioEngine")
        self._thread.start()
        logger.info("JarvisEngine started in background.")

    def stop(self) -> None:
        """Stop unified audio engine."""
        if not self._running:
            return
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("JarvisEngine stopped.")

    @property
    def is_running(self) -> bool:
        """Check if engine is running."""
        return self._running
