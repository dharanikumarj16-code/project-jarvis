import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import time
import difflib

try:
    import speech_recognition as sr
except ImportError:
    print("\n❌ CRITICAL ERROR: Missing Dependency")
    print("   The 'SpeechRecognition' library is required but not installed.")
    print("   Please run the following command to install it:")
    print("       pip install SpeechRecognition")
    print("   \n   Note: You may also need PyAudio for microphone access:")
    print("       pip install pyaudio\n")
    sys.exit(1)

from output.speech import speak

def listen(require_wake_word=True):
    """
    Voice to action pipeline step 1: Listen to user voice input
    Converts speech to text using Google's speech recognition
    If require_wake_word is True, only responds to commands that start with "Jarvis"
    Otherwise, returns any recognized text.
    """
    # Track last error time to prevent spamming the user
    if not hasattr(listen, "last_error_time"):
        listen.last_error_time = 0

    r = sr.Recognizer()
    r.pause_threshold = 1.2  # Wait 1.2s of silence before processing (Fixes "half word" cut off)
    r.non_speaking_duration = 0.5

    try:
        with sr.Microphone() as source:
            print("🎤 Calibrating... (please wait)")
            # Adjust for ambient noise
            r.adjust_for_ambient_noise(source, duration=0.5)
            print(f"🎤 Listening...")
            r.dynamic_energy_threshold = True
            audio = r.listen(source, timeout=5, phrase_time_limit=15)

        print("🔄 Processing speech...")
        text = r.recognize_google(audio)
        recognized_text = text.lower()
        print(f"👂 Heard: '{recognized_text}'")

        return recognized_text

    except sr.WaitTimeoutError:
        print("Jarvis: No speech detected within timeout period")
        return ""

    except sr.UnknownValueError:
        print("Jarvis: Could not understand the audio. Please try again.")
        return ""

    except sr.RequestError as e:
        print(f"Jarvis: Speech recognition service error: {e}")
        
        # Only speak the error if it's been more than 60 seconds since the last warning
        current_time = time.time()
        if current_time - listen.last_error_time > 60:
            speak("Speech recognition service is unavailable. Please check your internet connection.")
            listen.last_error_time = current_time
            
        return ""

    except Exception as e:
        print(f"Jarvis: Unexpected error in voice recognition: {e}")
        return ""
