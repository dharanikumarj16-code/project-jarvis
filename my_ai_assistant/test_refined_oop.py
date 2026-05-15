from core.jarvis_core import jarvis
import logging

# Configure logging to see the fallback messages
logging.basicConfig(level=logging.INFO)

def test_jarvis():
    print("Testing Mode Switching...")
    print(jarvis.process_command("switch to AI_WORK mode"))
    print(f"Current mode: {jarvis.current_mode}")
    
    print("\nTesting Trie Intent Detection (tell_time)...")
    # "time" is a keyword in Trie
    print(jarvis.process_command("what is the time"))
    
    print("\nTesting SearchWebCommand...")
    print(jarvis.process_command("google how to bake a cake"))
    
    print("\nTesting WhatsAppOpenChatCommand...")
    # This might require permissions if not in test mode, but let's see
    print(jarvis.process_command("open chat Kavi"))
    
    print("\nTesting Fallback to Legacy Brain...")
    # "read my tasks" should be detected by Trie and mapped to "read_tasks"
    # But "read_tasks" is NOT registered in registry_init.py (only add_task is)
    # So it should fall back to legacy brain
    print(jarvis.process_command("read my tasks"))

if __name__ == "__main__":
    test_jarvis()
