from input.voice import listen
from input.text import read_text
from core.brain import process_command
from core.memory import get_smart_suggestions, log_usage
from output.speech import speak
from core.scheduler import scheduler
from core.shortcuts_manager import lookup_shortcut
import random
import os
import sys
import threading
import time
import logging
import json

# Debug mode setup
DEBUG_MODE = os.getenv('JARVIS_DEBUG', 'false').lower() == 'true'
def setup_logging():
    """Setup logging for debugging"""
    log_level = logging.DEBUG if DEBUG_MODE else logging.INFO
    logging.basicConfig(
        filename='jarvis_debug.log',
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Also log to console in debug mode
    if DEBUG_MODE:
        console = logging.StreamHandler()
        console.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(levelname)s - %(message)s')
        console.setFormatter(formatter)
        logging.getLogger('').addHandler(console)

def debug_log(message, level='info'):
    """Log debug messages"""
    if DEBUG_MODE:
        if level == 'debug':
            logging.debug(message)
        elif level == 'warning':
            logging.warning(message)
        elif level == 'error':
            logging.error(message)
        else:
            logging.info(message)

# Global State
gui_app = None
interaction_count = 0
last_interaction_time = 0
CONVERSATION_TIMEOUT = 30 # Seconds to keep mic active without "Jarvis"

def process_single_command(command, source="voice"):
    """Unified command processor for Voice and UI"""
    global interaction_count, gui_app, last_interaction_time
    
    if not command: return

    # Normalize: Remove "jarvis" prefix if present (common in text input)
    if command.lower().startswith("jarvis"):
        command = command[6:].strip()

    # Update HUD to Executing
    if gui_app: 
        gui_app.set_state("executing")
        gui_app.show_message(None, "Processing...")
    
    print(f"User ({source}): {command}")
    debug_log(f"🧠 Processing command ({source}): '{command}'", 'debug')

    # Check for exit
    if command.lower() in ["exit", "quit", "stop"]:
        speak("Goodbye!")
        os._exit(0)

    # Check for Shortcut Queries first
    shortcut_response = lookup_shortcut(command)
    
    if shortcut_response:
        response = shortcut_response
    else:
        # Process standard commands
        response = process_command(command)
    
    # Output
    print(f"Jarvis: {response}")
    if gui_app:
        # Show output on the new screen overlay
        gui_app.show_message(command, response)
    if response:
        speak(response)
    
    # Log & Learn
    log_usage(command, True)
    interaction_count += 1
    last_interaction_time = time.time() # Keep conversation alive
    
    # Smart Suggestions (Occasional)
    if interaction_count % random.randint(3, 5) == 0:
        try:
            suggestions = get_smart_suggestions()
            if suggestions:
                suggestion = random.choice(suggestions)
                print(f"Jarvis: 💡 {suggestion}")
                speak(suggestion)
        except json.JSONDecodeError as e:
            debug_log(f"Failed to get smart suggestions due to JSON error: {e}", 'error')
            print("Jarvis: 💡 My learning data seems to be corrupted. I can't provide a suggestion right now.")
            speak("My learning data seems to be corrupted. I can't provide a suggestion right now.")

    # Reset HUD to Idle
    if gui_app: gui_app.set_state("idle")

def voice_listener_loop():
    """Background thread for continuous voice listening"""
    global gui_app, last_interaction_time
    print("🎤 Voice Listener started...")
    was_conversation_active = False
    
    while True:
        try:
            # Check if microphone is muted via UI
            if gui_app and not gui_app.listening_enabled:
                time.sleep(0.2)
                continue

            # Check if we are in active conversation mode
            is_conversation_active = (time.time() - last_interaction_time) < CONVERSATION_TIMEOUT
            
            # Visual feedback
            if gui_app: 
                if is_conversation_active:
                    gui_app.set_state("listening") # Orange (Active)
                else:
                    gui_app.set_state("idle") # Cyan (Waiting for "Jarvis")
                    
                    # Notify user when conversation mode ends (Timeout)
                    if was_conversation_active:
                        gui_app.show_message(None, "Microphone Standby")
            
            was_conversation_active = is_conversation_active
            
            # Listen (Require wake word only if timeout passed)
            command = listen(require_wake_word=not is_conversation_active)
            
            if command:
                # Strip "jarvis" prefix if present (listen() adds it in wake word mode)
                if command.lower().startswith("jarvis"):
                    actual_command = command[6:].strip()
                else:
                    actual_command = command.strip()
                
                if actual_command:
                    process_single_command(actual_command, source="voice")
                else:
                    # Just woke up
                    speak("Yes?")
                    last_interaction_time = time.time() # Start conversation timer

        except Exception as e:
            debug_log(f"Voice Error: {e}", 'error')
            if gui_app: gui_app.set_state("error")
            time.sleep(1)
            if gui_app: gui_app.set_state("idle")

def console_listener_loop():
    """Background thread for console text input"""
    print("⌨️ Console Command Mode enabled. Type commands here.")
    while True:
        try:
            command = input()
            if command.strip():
                process_single_command(command.strip(), source="console")
        except Exception:
            break

def main():
    """Main voice-to-action pipeline"""
    # Handle background execution (pythonw.exe) where stdout is None
    if sys.stdout is None:
        sys.stdout = open(os.devnull, 'w')
    if sys.stderr is None:
        sys.stderr = open(os.devnull, 'w')

    setup_logging()
    debug_log("🚀 Starting Jarvis AI Assistant", 'info')
    scheduler.start()

    print("🤖 Jarvis AI Assistant Started!")
    print("🚀 UI Mode: Check the Top-Right corner for the HUD.")
    if DEBUG_MODE:
        print("🐛 DEBUG MODE ENABLED - Check jarvis_debug.log for detailed logs")
    print("🎤 Voice-controlled, permission-based personal assistant with learning capabilities")
    print("💡 Try commands like:")
    print("   • 'Jarvis add task buy groceries'")
    print("   • 'Jarvis read my tasks'")
    print("   • 'Jarvis complete task 1'")
    print("   • 'Jarvis open notepad'")
    print("   • 'Jarvis what time is it'")
    print("   • 'Jarvis give me suggestions'")
    print("   • 'Jarvis exit' to stop")
    print("\nAlways start commands with 'Jarvis'. Say 'Jarvis exit' to stop.\n")

    speak("Jarvis is ready.")

    # Initialize UI
    from gui import JarvisGUI
    global gui_app
    
    # Callback for Command Bar
    gui_app = JarvisGUI(on_command=lambda text: process_single_command(text, source="ui"))

    # Start Voice Listener in Background Thread
    t = threading.Thread(target=voice_listener_loop, daemon=True)
    t.start()
    
    # Start Console Listener in Background Thread
    t_console = threading.Thread(target=console_listener_loop, daemon=True)
    t_console.start()
    
    # Start GUI (Blocking Main Thread)
    try:
        gui_app.start()
    except KeyboardInterrupt:
        print("\n🛑 Jarvis stopped by user.")
        os._exit(0)

if __name__ == "__main__":
    try:
        main()
    except json.JSONDecodeError:
        print("\n❌ CRITICAL ERROR: Memory Corruption Detected")
        print("   The assistant's memory file (JSON) is corrupted.")
        print("   Solution: Delete 'preferences.json' or 'tasks.json' in your project folder.")
        print("   The assistant will create a fresh one on next startup.")
        sys.exit(1)
                