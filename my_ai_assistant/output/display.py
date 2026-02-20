import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from output.speech import speak

def show(message):
    print("AI:", message)
    speak("AI:" + message)