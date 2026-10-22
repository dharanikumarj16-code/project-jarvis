import os


class VoiceConfig:
    # ── Global toggle ─────────────────────────────────────────────────
    VOICE_ENABLED = os.getenv("VOICE_ENABLED", "true").lower() == "true"

    # ── Wake word ─────────────────────────────────────────────────────
    WAKE_WORD_ENABLED = os.getenv("WAKE_WORD_ENABLED", "true").lower() == "true"
    WAKE_WORD = os.getenv("WAKE_WORD", "jarvis")

    # ── STT (faster-whisper / CTranslate2) ───────────────────────────
    STT_ENABLED = os.getenv("STT_ENABLED", "true").lower() == "true"
    STT_ENGINE = os.getenv("STT_ENGINE", "faster_whisper")
    # Model options (quality vs latency):
    #   tiny.en   ~39 MB  — fastest, lower accuracy
    #   base.en   ~74 MB  — good balance (recommended for assistants)
    #   small.en  ~244 MB — near human-level on clean audio
    #   distil-small.en — best quality/speed ratio for English
    STT_MODEL = os.getenv("STT_MODEL", "base.en")
    STT_DEVICE = os.getenv("STT_DEVICE", "cpu")      # "cpu" | "cuda" | "auto"
    STT_COMPUTE_TYPE = os.getenv("STT_COMPUTE_TYPE", "int8")  # "int8" | "float16"

    # ── STT streaming / endpointing tuning ───────────────────────────
    # Silence duration (ms) that triggers end-of-speech for short utterances
    STT_SHORT_SILENCE_MS = int(os.getenv("STT_SHORT_SILENCE_MS", "350"))
    # Silence duration (ms) for longer queries (> 1s of speech)
    STT_LONG_SILENCE_MS = int(os.getenv("STT_LONG_SILENCE_MS", "600"))
    # Greedy decoding beam size (1 = fastest, 5 = slightly more accurate)
    STT_BEAM_SIZE = int(os.getenv("STT_BEAM_SIZE", "1"))

    # ── VAD (Silero) ──────────────────────────────────────────────────
    VAD_ENABLED = os.getenv("VAD_ENABLED", "true").lower() == "true"
    # Speech probability threshold [0.0, 1.0] — raise to reduce false triggers
    VAD_THRESHOLD = float(os.getenv("VAD_THRESHOLD", "0.5"))

    # ── TTS ───────────────────────────────────────────────────────────
    TTS_ENABLED = os.getenv("TTS_ENABLED", "true").lower() == "true"
    TTS_ENGINE = os.getenv("TTS_ENGINE", "pyttsx3")

    # ── HUD ───────────────────────────────────────────────────────────
    HUD_ENABLED = os.getenv("HUD_ENABLED", "true").lower() == "true"
    HUD_ALWAYS_ON_TOP = os.getenv("HUD_ALWAYS_ON_TOP", "true").lower() == "true"

    # ── System ────────────────────────────────────────────────────────
    START_WITH_WINDOWS = os.getenv("START_WITH_WINDOWS", "false").lower() == "true"
