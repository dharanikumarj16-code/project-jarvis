import sys
import os
# Add project root to sys.path to allow running this script directly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json
import re
from google import genai
import PIL.Image
from core.permissions import ask_permission
def get_api_key():
    """
    Retrieve API key from environment or config file.
    """
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        # Try to read from config file
        config_file = os.path.join(os.path.dirname(__file__), '..', 'config.txt')
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                for line in f:
                    if line.startswith('GOOGLE_API_KEY='):
                        api_key = line.split('=', 1)[1].strip().strip('"').strip("'")
                        break
    return api_key

def setup_gemini_api():
    return bool(get_api_key())

def ask_gemini(prompt, context="", require_permission=True):
    """
    Integrate with Google Gemini for text generation and suggestions.
    This is used for drafting messages, generating summaries, etc.
    Does NOT control system actions directly.

    Args:
        prompt: The user's request for Gemini
        context: Additional context about the request
        require_permission: Whether to ask user for permission (default: True)

    Returns:
        Gemini response or error message
    """
    api_key = get_api_key()
    if not api_key:
        return "Gemini integration not configured. Please set GOOGLE_API_KEY environment variable or add it to config.txt"

    # Ask permission before making external API call
    if require_permission:
        action_description = f"send request to Gemini API for: '{prompt[:50]}...'"
        if not ask_permission(action_description):
            return "Gemini request cancelled by user."

    try:
        client = genai.Client(api_key=api_key)

        # Create a safe, limited prompt that emphasizes this is for assistance only
        safe_prompt = f"""
        You are a helpful assistant for text generation and suggestions.
        You CANNOT perform any system actions or control any devices.
        Your role is limited to generating text content only.

        User request: {prompt}
        {f'Context: {context}' if context else ''}

        Provide a helpful response focused on text generation, suggestions, or drafting.
        """

        response = client.models.generate_content(
            model='gemini-pro',
            contents=safe_prompt
        )

        return response.text.strip()

    except Exception as e:
        if "API_KEY_INVALID" in str(e):
            return "Configuration Error: Invalid Google API Key. Please check config.txt."
        return f"Gemini API error: {str(e)}"

# Chat history storage
chat_history = []

def chat_with_gemini(user_input, reset=False):
    """
    Continuous chat with Gemini maintaining context history.
    """
    global chat_history
    if reset:
        chat_history = []
        return "Chat history cleared."

    api_key = get_api_key()
    if not api_key:
        return "Gemini API key not found."

    try:
        client = genai.Client(api_key=api_key)
        
        # Build context from recent history (last 10 turns)
        history_context = "\n".join([f"User: {h['user']}\nAI: {h['ai']}" for h in chat_history[-10:]])
        
        prompt = f"""
        You are Jarvis, a helpful and intelligent AI assistant.
        Engage in a natural, helpful conversation.
        
        Previous conversation:
        {history_context}
        
        User: {user_input}
        AI:
        """
        
        response = client.models.generate_content(
            model='gemini-pro',
            contents=prompt
        )
        
        reply = response.text.strip()
        chat_history.append({"user": user_input, "ai": reply})
        return reply
        
    except Exception as e:
        return f"Error: {str(e)}"

def decide_intent(user_input):
    """
    Agentic Brain: Analyzes user input and decides the intent and parameters.
    Returns a JSON object with intent, args, and conversational response.
    """
    api_key = get_api_key()
    if not api_key:
        return {"intent": "error", "response_text": "Gemini API Key not found."}

    try:
        client = genai.Client(api_key=api_key)
        
        # Import here to avoid circular dependency
        from core.memory import get_learned_actions
        learned_actions = list(get_learned_actions().keys())
        
        prompt = f"""
        You are Jarvis, an advanced AI assistant.
        Analyze the user's input and decide the best action (intent) and extract parameters.
        
        User Input: "{user_input}"
        
        Available Intents:
        1. "chat": General conversation, greeting, or questions. (Return response in 'response_text')
        2. "add_task": Add a todo item. Args: 'description'.
        3. "read_tasks": List tasks. No args.
        4. "complete_task": Mark task done. Args: 'task_id' (integer) or 'task_desc'.
        5. "open_app": Open a desktop app. Args: 'app_name' (e.g., notepad, chrome).
        6. "search_web": Google search. Args: 'query'.
        7. "research_topic": Deep research. Args: 'topic'.
        8. "tell_time": Current time.
        9. "tell_date": Current date.
        10. "learn_action": User wants to teach a new automation. Args: 'action_name'.
        11. "execute_action": User wants to run a learned action. Args: 'action_name'.
            (Known learned actions: {', '.join(learned_actions)})
        12. "screen_analysis": User asks to look at/analyze screen.
        13. "camera_analysis": User asks to look at camera/photo.
        14. "complex_goal": Multi-step tasks requiring planning, reasoning, or using multiple tools. (e.g., "research X and write a summary", "organize my files", "plan a trip").
        
        Response Format (JSON ONLY):
        {{
            "intent": "intent_name",
            "args": {{ "arg_name": "value" }},
            "response_text": "Your conversational response here (required for 'chat' intent)"
        }}
        """
        
        response = client.models.generate_content(
            model='gemini-pro',
            contents=prompt
        )
        
        # Extract JSON from response
        text = response.text.strip()
        text = text.replace("```json", "").replace("```", "")
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return {"intent": "chat", "response_text": text}
        
    except Exception as e:
        print(f"Brain Error: {e}")
        return {"intent": "chat", "response_text": f"I encountered an error: {e}"}

def correct_speech_text(text):
    """
    Uses Gemini to correct potential speech-to-text errors based on context.
    This 'trains' the voice input to understand the user better.
    """
    prompt = f"""
    You are an advanced speech correction engine for an AI assistant named Jarvis. 
    Correct the following raw voice input for homophones, grammar, and context errors.
    
    Your goal is to map the user's speech to one of these valid command structures if possible:
    1. Task: "add task...", "read my tasks", "complete task..."
    2. System: "open notepad", "open browser", "open calculator", "open [app]"
    3. Info: "what time is it", "what date is it"
    4. AI: "ask chatgpt...", "ask gemini...", "draft message..."
    5. Web: "search for...", "research..."
    
    Example: "open no pad" -> "open notepad"
    Example: "at task by milk" -> "add task buy milk"
    
    Raw input: "{text}"
    Return ONLY the corrected text.
    """
    return ask_gemini(prompt, "Speech correction", require_permission=False)

def generate_smart_suggestion(task_description):
    """
    Use Gemini to generate smart suggestions for task completion.
    """
    prompt = f"Provide 2-3 practical suggestions for completing this task: {task_description}"
    return ask_gemini(prompt, "Task completion suggestions")

def summarize_web_content(query, content):
    """
    Summarize web search results or website content.
    """
    prompt = f"""
    I am researching: "{query}"
    Here is the raw data collected from the web:
    {content}
    
    Please provide a concise summary answering my research query based on this data.
    """
    return ask_gemini(prompt, "Web research summary")

def draft_email(subject, recipient="colleague"):
    """
    Use Gemini to draft professional emails.
    """
    prompt = f"Draft a professional email to a {recipient} with subject: {subject}"
    return ask_gemini(prompt, "Professional email drafting")

def analyze_image(prompt, image_path):
    """
    Use Gemini Vision capabilities to analyze an image.
    """
    api_key = get_api_key()
    if not api_key:
        return "Gemini integration not configured."

    if not os.path.exists(image_path):
        return "Image file not found."

    action_description = f"analyze an image using Gemini Vision"
    if not ask_permission(action_description):
        return "Image analysis cancelled."

    try:
        client = genai.Client(api_key=api_key)
        img = PIL.Image.open(image_path)
        response = client.models.generate_content(
            model='gemini-1.5-flash-002',
            contents=[prompt, img]
        )
        return response.text.strip()
    except Exception as e:
     if "API_KEY_INVALID" in str(e):
            return "Configuration Error: Invalid Google API Key. Please check config.txt."
     return f"Image analysis error: {str(e)}"

def parse_automation_command(command):
    """
    Parse a natural language command into a list of executable steps using Gemini.
    """
    api_key = get_api_key()
    if not api_key:
        return []

    prompt = f"""
    You are an automation parsing engine.
    Goal: Convert the user's natural language request into a strict JSON sequence of actions.
    
    User Request: "{command}"
    
    Available Actions:
    - "open": Launch an application. Value: app name (e.g., "whatsapp", "chrome").
    - "type": Type text. Value: the text string.
    - "press": Press a key or shortcut. Value: key name (e.g., "enter", "tab", "esc") or combo (e.g., "ctrl+c", "alt+f4", "win+r").
    - "click": Click the mouse. Value: "left", "right", or "double".
    - "wait": Pause execution. Value: duration in seconds (integer).
    
    Rules & Examples:
    1. If the user says "open [app]", generate: {{"action": "open", "value": "[app]"}}.
    2. If the user says "click [text]", interpret it as a "click" action (value "left").
    3. If the user says "text [message]" or "type [message]", generate: {{"action": "type", "value": "[message]"}}.
    4. For shortcuts like "copy that", generate: {{"action": "press", "value": "ctrl+c"}}.
    5. For "paste it", generate: {{"action": "press", "value": "ctrl+v"}}.
    6. For "lock the screen" or "lock computer", generate: {{"action": "press", "value": "win+l"}}.
    7. For "show desktop", generate: {{"action": "press", "value": "win+d"}}.
    8. For "open file explorer", generate: {{"action": "press", "value": "win+e"}}.
    9. For "open settings", generate: {{"action": "press", "value": "win+i"}}.
    10. For "take a screenshot", generate: {{"action": "press", "value": "win+shift+s"}}.
    11. For "switch windows", generate: {{"action": "press", "value": "alt+tab"}}.
    12. For "close window", generate: {{"action": "press", "value": "alt+f4"}}.
    13. Return ONLY a valid JSON list. Do not include markdown formatting.
    """
    
    # We use a direct client call here to avoid the 'ask_gemini' wrapper which restricts system actions
    if not ask_permission(f"analyze automation command using Gemini"):
        return []

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-pro',
            contents=prompt
        )
        
        text = response.text.strip()
        # Remove markdown code blocks if present
        text = text.replace("```json", "").replace("```", "")
        
        # Extract JSON
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception as e:
        if "API_KEY_INVALID" in str(e) or "API key not valid" in str(e):
            print("❌ Configuration Error: Invalid Google API Key. Please check config.txt.")
        else:
            print(f"Automation parsing error: {e}")
        pass
    return []