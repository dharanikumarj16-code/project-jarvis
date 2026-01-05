import os
import os.path
import google.generativeai as genai
from core.permissions import ask_permission

def setup_gemini_api():
    """
    Setup Gemini API with secure key management.
    API key should be stored in environment variable or config file.
    """
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        # Try to read from config file
        config_file = os.path.join(os.path.dirname(__file__), '..', 'config.txt')
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                for line in f:
                    if line.startswith('GOOGLE_API_KEY='):
                        api_key = line.split('=', 1)[1].strip()
                        break

    if api_key:
        genai.configure(api_key=api_key)
        return True
    return False

def ask_gemini(prompt, context=""):
    """
    Integrate with Google Gemini for text generation and suggestions.
    This is used for drafting messages, generating summaries, etc.
    Does NOT control system actions directly.

    Args:
        prompt: The user's request for Gemini
        context: Additional context about the request

    Returns:
        Gemini response or error message
    """
    if not setup_gemini_api():
        return "Gemini integration not configured. Please set GOOGLE_API_KEY environment variable or add it to config.txt"

    # Ask permission before making external API call
    action_description = f"send request to Gemini API for: '{prompt[:50]}...'"
    if not ask_permission(action_description):
        return "Gemini request cancelled by user."

    try:
        # Create a safe, limited prompt that emphasizes this is for assistance only
        safe_prompt = f"""
        You are a helpful assistant for text generation and suggestions.
        You CANNOT perform any system actions or control any devices.
        Your role is limited to generating text content only.

        User request: {prompt}
        {f'Context: {context}' if context else ''}

        Provide a helpful response focused on text generation, suggestions, or drafting.
        """

        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(safe_prompt)

        return response.text.strip()

    except Exception as e:
        return f"Gemini API error: {str(e)}"

def generate_smart_suggestion(task_description):
    """
    Use Gemini to generate smart suggestions for task completion.
    """
    prompt = f"Provide 2-3 practical suggestions for completing this task: {task_description}"
    return ask_gemini(prompt, "Task completion suggestions")

def draft_email(subject, recipient="colleague"):
    """
    Use Gemini to draft professional emails.
    """
    prompt = f"Draft a professional email to a {recipient} with subject: {subject}"
    return ask_gemini(prompt, "Professional email drafting")