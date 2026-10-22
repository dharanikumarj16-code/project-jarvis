"""
vad.py — Voice Activity Detection Engine (Silero VAD via ONNX Runtime)

Silero VAD processes 30ms frames at ~1ms/frame on CPU.
Used for:
  • Barge-in detection while assistant is speaking (fires an interruption event)
  • Real-time speech/silence gating in the audio loop
  • Feeding speech probability into STTEngine.transcribe_stream()
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE: int = 16_000
FRAME_SAMPLES: int = 512   # Silero VAD requirement: 512 samples @ 16 kHz = 32ms


class VADEngine:
    """
    Silero VAD wrapper.

    Falls back to an RMS-energy heuristic if silero-vad / torch
    is not installed, so the voice pipeline degrades gracefully.
    """

    def __init__(self, speech_threshold: float = 0.5) -> None:
        self.speech_threshold = speech_threshold
        self.is_speaking: bool = False
        self._model = None
        self._h: Optional[object] = None
        self._c: Optional[object] = None
        self._load_silero()

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def _load_silero(self) -> None:
        """Try to load Silero VAD via torch.hub (ONNX backend preferred)."""
        try:
            import torch
            model, _ = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                onnx=True,          # Use ONNX Runtime backend for lower overhead
                trust_repo=True,
            )
            if hasattr(model, "eval"):
                model.eval()
            self._model = model
            # Initialize LSTM hidden / cell states for PyTorch backend
            self._h = torch.zeros(2, 1, 64)
            self._c = torch.zeros(2, 1, 64)
            logger.info("VADEngine: Silero VAD (ONNX) loaded successfully.")
        except Exception as exc:
            logger.warning(
                "VADEngine: Silero VAD not available (%s). "
                "Falling back to RMS energy heuristic. "
                "Install with: pip install silero-vad",
                exc,
            )
            self._model = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_frame(self, audio_frame: np.ndarray) -> bool:
        """
        Evaluate a 30–32ms audio frame for speech.

        Args:
            audio_frame: float32 numpy array at 16 kHz, length ≥ 512 samples.

        Returns:
            True if speech is detected in this frame.
        """
        prob = self.speech_probability(audio_frame)
        self.is_speaking = prob >= self.speech_threshold
        return self.is_speaking

    def speech_probability(self, audio_frame: np.ndarray) -> float:
        """
        Return a speech probability [0.0, 1.0] for the given audio frame.

        Uses Silero VAD when available, otherwise RMS energy heuristic.
        """
        if self._model is not None:
            return self._silero_prob(audio_frame)
        return self._rms_prob(audio_frame)

    def reset(self) -> None:
        """Reset internal LSTM state (call between utterances)."""
        if self._model is not None:
            try:
                if hasattr(self._model, "reset_states"):
                    self._model.reset_states()
                import torch
                self._h = torch.zeros(2, 1, 64)
                self._c = torch.zeros(2, 1, 64)
            except Exception:
                pass
        self.is_speaking = False

    # ------------------------------------------------------------------
    # Internal: Silero ONNX evaluation
    # ------------------------------------------------------------------

    def _silero_prob(self, audio_frame: np.ndarray) -> float:
        try:
            import torch

            # Ensure correct dtype and shape
            if audio_frame.dtype != np.float32:
                audio_frame = audio_frame.astype(np.float32) / 32768.0

            # Pad / trim to FRAME_SAMPLES
            if len(audio_frame) < FRAME_SAMPLES:
                audio_frame = np.pad(
                    audio_frame, (0, FRAME_SAMPLES - len(audio_frame))
                )
            elif len(audio_frame) > FRAME_SAMPLES:
                audio_frame = audio_frame[:FRAME_SAMPLES]

            tensor = torch.from_numpy(audio_frame).unsqueeze(0)  # [1, 512]

            with torch.no_grad():
                if hasattr(self._model, "reset_states"):
                    prob = self._model(tensor, SAMPLE_RATE)
                else:
                    prob, self._h, self._c = self._model(
                        tensor, SAMPLE_RATE, self._h, self._c
                    )
            return float(prob.item() if hasattr(prob, "item") else prob)
        except Exception as exc:
            logger.debug("Silero eval error (using RMS fallback): %s", exc)
            return self._rms_prob(audio_frame)

    # ------------------------------------------------------------------
    # Internal: RMS energy fallback
    # ------------------------------------------------------------------

    @staticmethod
    def _rms_prob(audio_frame: np.ndarray) -> float:
        """
        RMS-energy-based speech probability.
        Threshold tuned for typical microphone noise floors at 16 kHz.
        """
        if len(audio_frame) == 0:
            return 0.0
        f32 = audio_frame.astype(np.float32)
        if f32.max() > 1.0:   # raw int16 range
            f32 = f32 / 32768.0
        rms = float(np.sqrt(np.mean(f32 ** 2)))
        # 0.015 = noise floor, 0.08 = clear speech — linear interpolation
        return float(np.clip((rms - 0.015) / (0.08 - 0.015), 0.0, 1.0))
