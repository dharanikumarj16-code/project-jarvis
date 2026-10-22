import sys
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QColor

from .events import event_bus, VoiceEvent
from .state import VoiceState

class Signals(QObject):
    state_changed = pyqtSignal(object)

class HUD(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel("⬤")
        self.label.setStyleSheet("color: gray; font-size: 30px; background-color: rgba(20,20,20,200); border-radius: 25px;")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setFixedSize(50, 50)
        self.layout.addWidget(self.label)
        self.setLayout(self.layout)
        
        self.resize(50, 50)
        
        self.signals = Signals()
        self.signals.state_changed.connect(self._update_ui)
        event_bus.subscribe("StateChanged", self._on_state_changed)

    def _on_state_changed(self, event: VoiceEvent):
        self.signals.state_changed.emit(event.data["state"])

    def _update_ui(self, state: VoiceState):
        colors = {
            VoiceState.IDLE: "gray",
            VoiceState.LISTENING_FOR_WAKE: "#4a90e2", # Blue
            VoiceState.LISTENING: "#2ecc71",          # Green
            VoiceState.THINKING: "#9b59b6",           # Purple
            VoiceState.SPEAKING: "#3498db",           # Cyan-blue
            VoiceState.EXECUTING: "#f39c12",          # Orange
            VoiceState.ERROR: "#e74c3c"               # Red
        }
        color = colors.get(state, "gray")
        self.label.setStyleSheet(f"color: {color}; font-size: 30px; background-color: rgba(20,20,20,200); border-radius: 25px;")

    def mousePressEvent(self, event):
        self.oldPos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        delta = event.globalPosition().toPoint() - self.oldPos
        self.move(self.x() + delta.x(), self.y() + delta.y())
        self.oldPos = event.globalPosition().toPoint()
