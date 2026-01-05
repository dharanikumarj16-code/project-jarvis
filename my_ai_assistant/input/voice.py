import speech_recognition as sr
from output.speech import speak

def listen():
    """
    Voice to action pipeline step 1: Listen to user voice input
    Converts speech to text using Google's speech recognition
    Only responds to commands that start with "Jarvis"
    """
    r = sr.Recognizer()

    try:
        with sr.Microphone() as source:
            print("🎤 Listening... (say 'Jarvis' followed by your command)")
            # Adjust for ambient noise
            r.adjust_for_ambient_noise(source, duration=0.5)
            audio = r.listen(source, timeout=5, phrase_time_limit=10)

        print("🔄 Processing speech...")
        text = r.recognize_google(audio)
        recognized_text = text.lower()
        print(f"You said: '{recognized_text}'")

        # Check if it starts with Jarvis
        if recognized_text.startswith("jarvis"):
            return recognized_text
        else:
            print("Jarvis: I only respond to commands that start with 'Jarvis'")
            return ""

    except sr.WaitTimeoutError:
        print("Jarvis: No speech detected within timeout period")
        return ""

    except sr.UnknownValueError:
        print("Jarvis: Could not understand the audio. Please try again.")
        speak("I couldn't understand that. Please start your command with 'Jarvis'.")
        return ""

    except sr.RequestError as e:
        print(f"Jarvis: Speech recognition service error: {e}")
        speak("Speech recognition service is unavailable. Please check your internet connection.")
        return ""

    except Exception as e:
        print(f"Jarvis: Unexpected error in voice recognition: {e}")
        return ""
