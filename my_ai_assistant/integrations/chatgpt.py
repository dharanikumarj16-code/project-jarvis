import os
import os.path
import openai
from core.permissions import ask_permission

def setup_chatgpt_api():
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
                        api_key = line.split('=', 1)[1].strip()
                        break

    if api_key:
        openai.api_key = api_key
        return True
    return False

def ask_chatgpt(prompt, context=""):
    """
    Integrate with ChatGPT for text generation and suggestions.
    This is used for drafting messages, generating summaries, etc.
    Does NOT control system actions directly.

    Args:
        prompt: The user's request for ChatGPT
        context: Additional context about the request

    Returns:
        ChatGPT response or error message
    """
    if not setup_chatgpt_api():
        return "ChatGPT integration not configured. Please set OPENAI_API_KEY environment variable or add it to config.txt"

    # Ask permission before making external API call
    action_description = f"send request to ChatGPT API for: '{prompt[:50]}...'"
    if not ask_permission(action_description):
        return "ChatGPT request cancelled by user."

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

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # Using GPT-3.5 for cost effectiveness
            messages=[
                {"role": "system", "content": "You are a text generation assistant. You cannot perform system actions."},
                {"role": "user", "content": safe_prompt}
            ],
            max_tokens=500,  # Limit response length
            temperature=0.7  # Balanced creativity
        )

        return response.choices[0].message.content.strip()

    except openai.error.OpenAIError as e:
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