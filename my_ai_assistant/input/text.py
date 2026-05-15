import pyttsx3

engine = pyttsx3.init()

def read_text(text):
    engine.say(text)
    engine.runAndWait()
