from dataclasses import dataclass
from typing import Any, Callable

@dataclass
class VoiceEvent:
    name: str
    data: dict[str, Any] = None

class EventBus:
    def __init__(self):
        self.subscribers: dict[str, list[Callable]] = {}

    def subscribe(self, event_name: str, callback: Callable):
        if event_name not in self.subscribers:
            self.subscribers[event_name] = []
        self.subscribers[event_name].append(callback)

    def publish(self, event: VoiceEvent):
        if event.name in self.subscribers:
            for callback in self.subscribers[event.name]:
                try:
                    callback(event)
                except Exception as e:
                    print(f"Error in event subscriber for {event.name}: {e}")

event_bus = EventBus()
