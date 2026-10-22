"""
manager.py — VoiceManager

Orchestrates the full Google Assistant-style voice loop:

  ┌────────────────────────────────────────────────────────────────┐
  │  PyAudio stream  →  30ms INT16 chunks                          │
  │        │                                                        │
  │  VADEngine.process_frame()  →  barge-in / speech detection     │
  │        │                                                        │
  │  WakeWordEngine.process_frame()  (when LISTENING_FOR_WAKE)     │
  │        │                                                        │
  │  STTEngine.transcribe_stream()  →  endpoint → CommandReceived  │
  └────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Optional

import numpy as np

from .config import VoiceConfig
from .events import VoiceEvent, event_bus
from .state import VoiceState
from .tts import TTSManager
from .stt import STTEngine, CHUNK_SAMPLES, SAMPLE_RATE
from .vad import VADEngine
from .wake_word import WakeWordEngine

logger = logging.getLogger(__name__)


class VoiceManager:
    """
    Central voice pipeline manager.

    State machine:
        IDLE → LISTENING_FOR_WAKE → WAKE_DETECTED → LISTENING
             → TRANSCRIBING → THINKING → SPEAKING → LISTENING_FOR_WAKE
    """

    def __init__(self) -> None:
        self.state = VoiceState.IDLE
        self.config = VoiceConfig()

        # Engines
        self.tts = TTSManager() if self.config.TTS_ENABLED else None
        self.stt = STTEngine() if self.config.STT_ENABLED else None
        self.vad = VADEngine() if self.config.VAD_ENABLED else None
        self.wake_word = (
            WakeWordEngine(self.config.WAKE_WORD)
            if self.config.WAKE_WORD_ENABLED
            else None
        )

        # Wire STT async transcript callback → CommandReceived event
        if self.stt:
            self.stt.set_on_transcript(self._on_transcript_ready)

        self.running = False
        self._stream = None  # PyAudio stream handle

        self._thread = threading.Thread(
            target=self._audio_loop, daemon=True, name="voice-manager"
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        self.running = True
        self.set_state(VoiceState.LISTENING_FOR_WAKE)
        self._thread.start()
        logger.info("VoiceManager started.")

    def stop(self) -> None:
        self.running = False
        self.set_state(VoiceState.STOPPED)
        if self.tts:
            self.tts.shutdown()
        logger.info("VoiceManager stopped.")

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def set_state(self, new_state: VoiceState) -> None:
        if self.state != new_state:
            logger.debug("VoiceState: %s → %s", self.state.name, new_state.name)
            self.state = new_state
            event_bus.publish(VoiceEvent("StateChanged", {"state": self.state}))

    # ------------------------------------------------------------------
    # Command entry-points
    # ------------------------------------------------------------------

    def process_command(self, text: str) -> None:
        """Called when a full transcript is ready (text-mode or STT)."""
        self.set_state(VoiceState.THINKING)
        event_bus.publish(VoiceEvent("CommandReceived", {"text": text}))

    def _on_transcript_ready(self, text: str) -> None:
        """STT async callback — fires from STT worker thread."""
        if not text:
            return
        logger.info("STT transcript: %r", text)
        self.set_state(VoiceState.TRANSCRIBING)
        self.process_command(text)

    # ------------------------------------------------------------------
    # Audio loop — Google Assistant-style streaming pipeline
    # ------------------------------------------------------------------

    def _audio_loop(self) -> None:
        """
        Main audio capture + processing loop.

        Reads 30ms PCM INT16 chunks from the microphone and routes them
        through:
          1. VAD → barge-in detection while SPEAKING
          2. WakeWordEngine → trigger LISTENING state
          3. STTEngine.transcribe_stream() → endpoint → transcript
        """
        try:
            import pyaudio
        except ImportError:
            logger.error(
                "PyAudio not installed. Voice input unavailable. "
                "Install with: pip install pyaudio"
            )
            return

        pa = pyaudio.PyAudio()
        try:
            stream = pa.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=CHUNK_SAMPLES,
            )
            self._stream = stream
            logger.info(
                "Audio stream opened: %d Hz, %d sample chunks (%.0f ms)",
                SAMPLE_RATE, CHUNK_SAMPLES, CHUNK_SAMPLES / SAMPLE_RATE * 1000,
            )
        except Exception as exc:
            logger.error("Failed to open audio stream: %s", exc)
            pa.terminate()
            return

        while self.running:
            # ── 1. Read one 30ms chunk ─────────────────────────────
            try:
                raw = stream.read(CHUNK_SAMPLES, exception_on_overflow=False)
            except Exception as exc:
                logger.debug("Stream read error: %s", exc)
                continue

            chunk = np.frombuffer(raw, dtype=np.int16)
            chunk_f32 = chunk.astype(np.float32) / 32768.0

            # ── 2. VAD — always running ────────────────────────────
            is_speech = self.vad.process_frame(chunk_f32) if self.vad else True

            # ── 3. Barge-in: user speaks while assistant talks ─────
            if self.state == VoiceState.SPEAKING and is_speech:
                logger.info("Barge-in detected — interrupting TTS.")
                if self.tts:
                    self.tts.stop()  # type: ignore[attr-defined]
                if self.vad:
                    self.vad.reset()
                self.set_state(VoiceState.LISTENING)

            # ── 4. Wake word detection ─────────────────────────────
            if self.state == VoiceState.LISTENING_FOR_WAKE:
                if self.wake_word and self.wake_word.process_frame(chunk_f32):
                    logger.info("Wake word detected.")
                    self.set_state(VoiceState.LISTENING)
                    if self.vad:
                        self.vad.reset()
                    if self.stt:
                        self.stt._reset_state()  # clear any stale buffer
                continue  # don't feed wake-word audio to STT

            # ── 5. STT streaming (only in LISTENING state) ─────────
            if self.state == VoiceState.LISTENING and self.stt:
                result = self.stt.transcribe_stream(chunk)
                # Note: result will be None here because transcription is async.
                # The actual transcript arrives via _on_transcript_ready callback.

        # Cleanup
        stream.stop_stream()
        stream.close()
        pa.terminate()
        logger.info("Audio stream closed.")
