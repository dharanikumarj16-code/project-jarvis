import sys
import os

# Add project root to sys.path to fix ModuleNotFoundError
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from openai import OpenAI, OpenAIError
except ImportError:
    print("⚠️ OpenAI library not found. Run: pip install openai")
    OpenAI = None
    OpenAIError = Exception
from core.permissions import ask_permission

def get_api_key():
    """
    Setup ChatGPT API with secure key management.
    API key should be stored in environment variable or config file.
    """
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        # Try to read from config file
        config_file = os.path.join(os.path.dirname(__file__), '..', 'config.txt')
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                for line in f:
                    if line.startswith('OPENAI_API_KEY='):
                        api_key = line.split('=', 1)[1].strip().strip('"').strip("'")
                        break

    return api_key

def setup_chatgpt_api():
    return bool(get_api_key()) and (OpenAI is not None)

def ask_chatgpt(prompt, context="", require_permission=True):
    """
    Integrate with ChatGPT for text generation and suggestions.
    This is used for drafting messages, generating summaries, etc.
    Does NOT control system actions directly.

    Args:
        prompt: The user's request for ChatGPT
        context: Additional context about the request
        require_permission: Whether to ask user for permission (default: True)

    Returns:
        ChatGPT response or error message
    """
    if OpenAI is None:
        return "OpenAI library not installed. Please run: pip install openai"

    api_key = get_api_key()
    if not api_key:
        return "ChatGPT integration not configured. Please set OPENAI_API_KEY environment variable or add it to config.txt"

    # Ask permission before making external API call
    if require_permission:
        action_description = f"send request to ChatGPT API for: '{prompt[:50]}...'"
        if not ask_permission(action_description):
            return "ChatGPT request cancelled by user."

    try:
        client = OpenAI(api_key=api_key)

        # Create a safe, limited prompt that emphasizes this is for assistance only
        safe_prompt = f"""
        You are a helpful assistant for text generation and suggestions.
        You CANNOT perform any system actions or control any devices.
        Your role is limited to generating text content only.

        User request: {prompt}
        {f'Context: {context}' if context else ''}

        Provide a helpful response focused on text generation, suggestions, or drafting.
        """

        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Updated to GPT-4o-mini (Cheaper & Better than 3.5)
            messages=[
                {"role": "system", "content": "You are a text generation assistant. You cannot perform system actions."},
                {"role": "user", "content": safe_prompt}
            ],
            max_tokens=500,  # Limit response length
            temperature=0.7  # Balanced creativity
        )

        return response.choices[0].message.content.strip()

    except OpenAIError as e:
        return f"ChatGPT API error: {str(e)}"
    except Exception as e:
        return f"Unexpected error with ChatGPT: {str(e)}"

def generate_task_summary(tasks_list):
    """
    Use ChatGPT to generate a summary of tasks.
    This is a productivity feature.
    """
    if not tasks_list:
        return "No tasks to summarize."

    prompt = f"Summarize these daily tasks in a concise, organized way: {tasks_list}"
    return ask_chatgpt(prompt, "Task summarization for productivity")

def draft_message(topic, tone="professional"):
    """
    Use ChatGPT to draft messages or notes.
    """
    prompt = f"Draft a {tone} message about: {topic}"
    return ask_chatgpt(prompt, f"Message drafting in {tone} tone")

if __name__ == "__main__":
    print("🤖 Testing ChatGPT Connection...")
    if setup_chatgpt_api():
        print("✅ API Key found. Sending test request...")
        print(f"💬 Response: {ask_chatgpt('Hello, are you online?', require_permission=False)}")
    else:
        print("❌ Setup failed. Please check config.txt and run: pip install openai")