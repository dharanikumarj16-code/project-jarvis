from output.speech import speak

def show(message):
    print("AI:", message)
    speak("AI:" + message)