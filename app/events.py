from typing import Callable, Dict, List, Any
import asyncio

class EventBus:
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_name: str, callback: Callable):
        if event_name not in self.subscribers:
            self.subscribers[event_name] = []
        self.subscribers[event_name].append(callback)

    async def publish(self, event_name: str, data: Any = None):
        if event_name in self.subscribers:
            for callback in self.subscribers[event_name]:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event_name, data)
                else:
                    callback(event_name, data)

event_bus = EventBus()
