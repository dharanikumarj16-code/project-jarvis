import os
import wave
import pyaudio
import math
import struct
from dotenv import load_dotenv
from groq import Groq
import time

load_dotenv()

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
WAVE_OUTPUT_FILENAME = "temp_voice.wav"

def get_rms(data):
    """Calculate RMS of audio chunk."""
    count = len(data) // 2
    if count == 0: return 0
    format_string = f"<{count}h"
    shorts = struct.unpack(format_string, data)
    sum_squares = sum(s * s for s in shorts)
    return math.sqrt(sum_squares / count)

def record_audio(threshold=300, silence_limit=1.5, max_duration=10.0, timeout=None):
    """Records audio until silence is detected. If timeout is set and no speech is heard, returns None."""
    p = pyaudio.PyAudio()
    
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)
                    
    print("\n[VAD] Listening for speech...")
    frames = []
    
    started = False
    silent_chunks = 0
    max_silent_chunks = int((RATE / CHUNK) * silence_limit)
    max_total_chunks = int((RATE / CHUNK) * max_duration)
    total_chunks = 0
    start_time = time.time()
    
    while True:
        try:
            data = stream.read(CHUNK, exception_on_overflow=False)
        except:
            continue
            
        rms = get_rms(data)
        total_chunks += 1
        
        if rms > threshold:
            if not started:
                print(f"[VAD] Speech started! (RMS: {int(rms)})")
                started = True
            silent_chunks = 0
        else:
            if started:
                silent_chunks += 1
                
        if started:
            frames.append(data)
            
        if started and silent_chunks > max_silent_chunks:
            print("[VAD] Silence detected, stopping recording.")
            break
            
        if total_chunks > max_total_chunks and started:
            print("[VAD] Max duration reached.")
            break
            
        if not started and timeout and (time.time() - start_time) > timeout:
            print("[VAD] Timeout reached, no speech detected.")
            break
            
    stream.stop_stream()
    stream.close()
    p.terminate()
    
    if not frames:
        return None
        
    wf = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()
    
    return WAVE_OUTPUT_FILENAME

def transcribe_audio(filename):
    if not filename or not os.path.exists(filename):
        return ""
    print("Transcribing with Groq Whisper...")
    client = Groq()
    try:
        with open(filename, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(filename, file.read()),
                model="whisper-large-v3",
            )
        return transcription.text
    except Exception as e:
        print(f"Transcription error: {e}")
        return ""
