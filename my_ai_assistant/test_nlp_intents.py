from core.brain import process_command, current_mode
import core.brain as brain

def test_nlp_integration():
    print(f"Current Mode: {brain.current_mode}")
    
    # Test 1: Task command in General mode (should work)
    print("\nTest 1: 'add task buy milk' in GENERAL mode")
    response = process_command("add task buy milk")
    print(f"Response: {response}")
    
    # Test 2: Switch to Music Mode
    print("\nTest 2: 'switch to music mode'")
    response = process_command("switch to music mode")
    print(f"Response: {response}")
    print(f"Current Mode: {brain.current_mode}")
    
    # Test 3: Music command in Music mode (should work)
    print("\nTest 3: 'play some music' in MUSIC_MODE")
    response = process_command("play some music")
    print(f"Response: {response}")
    
    # Test 4: Lights command in Music mode (should trigger mode mismatch)
    print("\nTest 4: 'turn off the lights' in MUSIC_MODE")
    response = process_command("turn off the lights")
    print(f"Response: {response}")
    
    # Test 5: Switch to Home Automation mode
    print("\nTest 5: 'switch to home automation mode'")
    response = process_command("switch to home automation mode")
    print(f"Response: {response}")
    print(f"Current Mode: {brain.current_mode}")

if __name__ == "__main__":
    # Mocking some dependencies to avoid errors during test
    import os
    os.environ['JARVIS_DEBUG'] = 'true'
    
    try:
        test_nlp_integration()
    except Exception as e:
        print(f"Error during test: {e}")
