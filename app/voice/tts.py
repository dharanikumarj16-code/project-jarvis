import pyttsx3
import threading
import queue
from .events import event_bus, VoiceEvent
from .state import VoiceState

class TTSManager:
    def __init__(self):
        self.engine = pyttsx3.init()
        self.engine.setProperty('rate', 170)
        self.speech_queue = queue.Queue()
        self.is_speaking = False
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()
        
        event_bus.subscribe("Interrupted", self._on_interrupt)

    def speak(self, text: str):
        if not text:
            return
        self.speech_queue.put(text)

    def _on_interrupt(self, event: VoiceEvent):
        with self.speech_queue.mutex:
            self.speech_queue.queue.clear()
        if self.is_speaking:
            try:
                self.engine.stop()
            except:
                pass

    def _worker(self):
        while True:
            text = self.speech_queue.get()
            if text:
                self.is_speaking = True
                event_bus.publish(VoiceEvent("StateChanged", {"state": VoiceState.SPEAKING}))
                try:
                    self.engine.say(text)
                    self.engine.runAndWait()
                except Exception as e:
                    event_bus.publish(VoiceEvent("VoiceError", {"error": f"TTS Error: {e}"}))
                self.is_speaking = False
                event_bus.publish(VoiceEvent("StateChanged", {"state": VoiceState.IDLE}))
            self.speech_queue.task_done()

    def shutdown(self):
        self._on_interrupt(None)
