import pyttsx3

engine = pyttsx3.init()
engine.setProperty('rate', 170)   # speaking speed
engine.setProperty('volume', 1.0) # volume

def speak(text):
    engine.say(text)
    engine.runAndWait()
    speak("AI:" + text)