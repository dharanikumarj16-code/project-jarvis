import time
import os
import sys
import asyncio
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.agent import get_agent, build_dynamic_tools
from app.tools.registry import register_all_tools

def benchmark_agent_rebuild():
    print("--- Benchmarking agent rebuild (get_agent) ---")
    # Register tools first so the bus has them
    register_all_tools()
    
    categories = ["SYSTEM", "CORE", "WINDOWS", "INPUT", "FILESYSTEM", "BROWSER"]
    
    # Warmup
    get_agent()
    
    times = []
    for i in range(5):
        start = time.perf_counter()
        get_agent()
        duration = (time.perf_counter() - start) * 1000
        times.append(duration)
        print(f"Run {i+1}: {duration:.2f} ms")
        
    avg = sum(times) / len(times)
    print(f"Average agent rebuild time: {avg:.2f} ms\\n")

def benchmark_tts():
    print("--- Benchmarking TTS blocking ---")
    try:
        from app.voice.tts import TTSManager
        tts = TTSManager()
        start = time.perf_counter()
        print("Speaking short phrase...")
        tts.speak("This is a test of the text to speech engine.")
        duration = (time.perf_counter() - start) * 1000
        print(f"TTS blocking time: {duration:.2f} ms\\n")
    except Exception as e:
        print(f"TTS benchmark skipped/failed: {e}\\n")

if __name__ == "__main__":
    benchmark_agent_rebuild()
    benchmark_tts()
