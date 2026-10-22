class WakeWordEngine:
    def __init__(self, wake_word="jarvis"):
        self.wake_word = wake_word.lower()
        # In a full production build, we would load an openwakeword .tflite model here.
        # For this robust abstraction, we provide the detection interface.
        pass

    def process_frame(self, audio_frame) -> bool:
        """
        Process a chunk of audio. Returns True if wake word is detected.
        """
        # Mock implementation for abstraction
        return False
