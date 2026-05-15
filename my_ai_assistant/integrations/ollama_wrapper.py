import requests
import json
import os

def get_ollama_model():
    """
    Retrieve Ollama model from environment or config file.
    """
    model = os.getenv('OLLAMA_MODEL', 'llama3')
    config_file = os.path.join(os.path.dirname(__file__), '..', 'config.txt')
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            for line in f:
                if line.startswith('OLLAMA_MODEL='):
                    model = line.split('=', 1)[1].strip().strip('"').strip("'")
                    break
    return model

def safety_filter(command):
    """
    Analyzes the command for potential safety risks before execution.
    Returns True if safe, False otherwise.
    """
    # Basic keyword filtering for safety
    unsafe_keywords = [
        "rm -rf", "format", "delete system32", "wipe", 
        "shutdown", "reboot", "mkfs", ":(){ :|:& };:"
    ]
    
    command_lower = command.lower()
    for keyword in unsafe_keywords:
        if keyword in command_lower:
            return False
            
    return True

def execute_agent_goal(goal):
    """
    Routes complex goals to the local Ollama AI.
    """
    if not safety_filter(goal):
        return "Command rejected for safety reasons."

    model = get_ollama_model()
    
    try:
        # Assuming Ollama is running locally on default port
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": goal,
                "stream": False
            },
            timeout=60
        )
        response.raise_for_status()
        result = response.json()
        return result.get("response", "No response from Ollama.")
    except Exception as e:
        return f"Ollama Error: {str(e)}. Make sure Ollama is running (ollama serve) and model '{model}' is pulled."
