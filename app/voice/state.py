from enum import Enum, auto

class VoiceState(Enum):
    IDLE = auto()
    LISTENING_FOR_WAKE = auto()
    WAKE_DETECTED = auto()
    LISTENING = auto()
    TRANSCRIBING = auto()
    THINKING = auto()
    PLANNING = auto()
    WAITING_APPROVAL = auto()
    EXECUTING = auto()
    SPEAKING = auto()
    INTERRUPTED = auto()
    ERROR = auto()
    STOPPED = auto()
