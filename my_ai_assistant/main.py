
from input.voice import listen
from core.brain import process_command
from core.memory import get_smart_suggestions, log_usage
from output.speech import speak
import random
import os
import logging

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

def main():
    """Main voice-to-action pipeline"""
    setup_logging()
    debug_log("🚀 Starting Jarvis AI Assistant", 'info')

    print("🤖 Jarvis AI Assistant Started!")
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

    speak("Jarvis is ready. How can I help you today?")

    interaction_count = 0
    error_count = 0

    while True:
        try:
            debug_log(f"🎤 Listening for command #{interaction_count + 1}", 'debug')
            command = listen()

            if not command:  # Skip empty commands
                debug_log("⚠️  Empty command received, skipping", 'debug')
                continue

            debug_log(f"📝 Raw command received: '{command}'", 'debug')

            # Check if command starts with "Jarvis"
            if command.lower().startswith("jarvis"):
                # Extract the actual command after "Jarvis"
                actual_command = command[6:].strip()  # Remove "Jarvis" and any leading space

                debug_log(f"🎯 Processed command: '{actual_command}'", 'debug')

                # If just "Jarvis" is said without command
                if not actual_command:
                    debug_log("👋 Just 'Jarvis' called without command", 'debug')
                    print("Jarvis: Yes? How can I help you?")
                    speak("Yes? How can I help you?")
                    continue
            else:
                debug_log(f"🚫 Command doesn't start with Jarvis: '{command}'", 'debug')
                continue

            if actual_command == "exit":
                debug_log("👋 Exit command received, shutting down", 'info')
                print("Jarvis: Goodbye!")
                speak("Goodbye! Have a great day!")
                break

            # Process command and get response
            debug_log(f"🧠 Processing command: '{actual_command}'", 'debug')
            response = process_command(actual_command)

            if response == "exit":  # Handle exit from brain
                debug_log("👋 Exit response from brain, shutting down", 'info')
                print("Jarvis: Goodbye!")
                speak("Goodbye!")
                break

            debug_log(f"💬 Response generated: '{response}'", 'debug')
            print(f"Jarvis: {response}")
            speak(response)

            # Log successful command usage
            log_usage(actual_command, True)
            interaction_count += 1
            debug_log(f"✅ Command processed successfully. Total interactions: {interaction_count}", 'debug')

            # Occasionally offer smart suggestions (every 3-5 interactions)
            if interaction_count % random.randint(3, 5) == 0:
                debug_log("💡 Checking for smart suggestions", 'debug')
                suggestions = get_smart_suggestions()
                if suggestions and len(suggestions) > 0:
                    proactive_suggestion = random.choice(suggestions)
                    debug_log(f"💡 Offering suggestion: '{proactive_suggestion}'", 'debug')
                    print(f"Jarvis: 💡 {proactive_suggestion}")
                    speak(proactive_suggestion)

        except KeyboardInterrupt:
            debug_log("🛑 Keyboard interrupt received, shutting down gracefully", 'info')
            print("\nJarvis: Goodbye!")
            speak("Goodbye!")
            break
        except Exception as e:
            error_count += 1
            debug_log(f"❌ Error in main loop: {str(e)}", 'error')
            print(f"Jarvis: I encountered an error: {str(e)}")
            if DEBUG_MODE:
                print(f"Debug: Error details logged to jarvis_debug.log")
            speak("I encountered an error. Please try again.")

            # If too many errors, suggest restart
            if error_count > 5:
                debug_log("🚨 Too many errors, suggesting restart", 'warning')
                print("Jarvis: I've encountered several errors. You might want to restart me.")
                speak("I've encountered several errors. You might want to restart me.")

    debug_log(f"🏁 Jarvis shutdown. Total interactions: {interaction_count}, Errors: {error_count}", 'info')

if __name__ == "__main__":
    main()
from input.voice import listen
from core.brain import process_command