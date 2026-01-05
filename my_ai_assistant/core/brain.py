from core.permissions import ask_permission, get_permission_history
from core.memory import add_task, get_tasks, complete_task, log_usage, get_smart_suggestions, update_task_priorities, predict_task_priority
from integrations.chatgpt import ask_chatgpt, generate_task_summary, draft_message
from integrations.gemini import ask_gemini, generate_smart_suggestion, draft_email
import os
import webbrowser
import datetime
import re
import logging

DEBUG_MODE = os.getenv('JARVIS_DEBUG', 'false').lower() == 'true'

def debug_log(message, level='info'):
    """Log debug messages"""
    if DEBUG_MODE:
        if level == 'debug':
            logging.debug(f"[BRAIN] {message}")
        elif level == 'warning':
            logging.warning(f"[BRAIN] {message}")
        elif level == 'error':
            logging.error(f"[BRAIN] {message}")
        else:
            logging.info(f"[BRAIN] {message}")

def classify_command(command):
    """Simple command classification system"""
    debug_log(f"Classifying command: '{command}'", 'debug')
    command = command.lower().strip()

    # Task management commands
    if command.startswith("add task") or "add a task" in command:
        debug_log("Classified as: add_task", 'debug')
        return "add_task"
    if "read my tasks" in command or "list tasks" in command or "show tasks" in command:
        debug_log("Classified as: read_tasks", 'debug')
        return "read_tasks"
    if "complete task" in command or "finish task" in command:
        debug_log("Classified as: complete_task", 'debug')
        return "complete_task"

    # System control commands
    if "open notepad" in command:
        debug_log("Classified as: open_notepad", 'debug')
        return "open_notepad"
    if "open browser" in command or "open chrome" in command:
        debug_log("Classified as: open_browser", 'debug')
        return "open_browser"
    if "open calculator" in command:
        debug_log("Classified as: open_calculator", 'debug')
        return "open_calculator"

    # Information commands
    if "time" in command or "what time" in command:
        debug_log("Classified as: tell_time", 'debug')
        return "tell_time"
    if "date" in command or "what date" in command:
        debug_log("Classified as: tell_date", 'debug')
        return "tell_date"
    if "permission history" in command or "show permissions" in command:
        debug_log("Classified as: permission_history", 'debug')
        return "permission_history"

    # AI Integration commands
    if "ask chatgpt" in command or "use chatgpt" in command:
        debug_log("Classified as: chatgpt_query", 'debug')
        return "chatgpt_query"
    if "ask gemini" in command or "use gemini" in command:
        debug_log("Classified as: gemini_query", 'debug')
        return "gemini_query"
    if "summarize tasks" in command or "task summary" in command:
        debug_log("Classified as: task_summary", 'debug')
        return "task_summary"
    if "draft message" in command or "write message" in command:
        debug_log("Classified as: draft_message", 'debug')
        return "draft_message"
    if "suggest" in command and "task" in command:
        debug_log("Classified as: task_suggestion", 'debug')
        return "task_suggestion"
    if "draft email" in command or "write email" in command:
        debug_log("Classified as: draft_email", 'debug')
        return "draft_email"

    # Learning AI commands
    if "smart suggestions" in command or "give me suggestions" in command or "what should i do" in command:
        debug_log("Classified as: smart_suggestions", 'debug')
        return "smart_suggestions"
    if "update priorities" in command or "learn priorities" in command:
        debug_log("Classified as: update_priorities", 'debug')
        return "update_priorities"
    if "analyze patterns" in command or "show patterns" in command:
        debug_log("Classified as: analyze_patterns", 'debug')
        return "analyze_patterns"

    debug_log("Classified as: unknown", 'debug')
    return "unknown"

def process_command(command):
    """Main command processing with improved classification"""
    intent = classify_command(command)

    if intent == "add_task":
        # Extract task description after "add task"
        task_desc = re.sub(r'^add task\s*', '', command, flags=re.IGNORECASE).strip()
        if not task_desc:
            return "Please specify what task to add. Say 'add task [description]'"
        result = add_task(task_desc)
        log_usage("add_task", True)
        return result

    elif intent == "read_tasks":
        return get_tasks()

    elif intent == "complete_task":
        # Extract task number
        match = re.search(r'(\d+)', command)
        if match:
            task_id = int(match.group(1))
            return complete_task(task_id)
        return "Please specify which task number to complete. Say 'complete task [number]'"

    elif intent == "open_notepad":
        if ask_permission("open Notepad"):
            os.system("notepad")
            return "Notepad opened successfully"
        return "Permission denied for opening Notepad"

    elif intent == "open_browser":
        if ask_permission("open web browser"):
            webbrowser.open("https://google.com")
            return "Browser opened successfully"
        return "Permission denied for opening browser"

    elif intent == "open_calculator":
        if ask_permission("open Calculator"):
            os.system("calc")
            return "Calculator opened successfully"
        return "Permission denied for opening Calculator"

    elif intent == "tell_time":
        current_time = datetime.datetime.now().strftime("%I:%M %p")
        return f"The current time is {current_time}"

    elif intent == "tell_date":
        current_date = datetime.datetime.now().strftime("%B %d, %Y")
        return f"Today's date is {current_date}"

    elif intent == "permission_history":
        history = get_permission_history()
        if history == "No permission history found.":
            return "No permission decisions have been logged yet."
        return f"Permission History:\n{history}"

    elif intent == "chatgpt_query":
        # Extract query after "ask chatgpt" or similar
        query = re.sub(r'^(ask|use)\s+chatgpt\s+', '', command, flags=re.IGNORECASE).strip()
        if not query:
            return "Please specify what you want to ask ChatGPT. Say 'ask ChatGPT [your question]'"
        return ask_chatgpt(query)

    elif intent == "gemini_query":
        # Extract query after "ask gemini" or similar
        query = re.sub(r'^(ask|use)\s+gemini\s+', '', command, flags=re.IGNORECASE).strip()
        if not query:
            return "Please specify what you want to ask Gemini. Say 'ask Gemini [your question]'"
        return ask_gemini(query)

    elif intent == "task_summary":
        tasks = get_tasks()
        if "No tasks found" in tasks:
            return "You don't have any tasks to summarize."
        return generate_task_summary(tasks)

    elif intent == "draft_message":
        # Extract topic after "draft message"
        topic = re.sub(r'^draft\s+message\s+', '', command, flags=re.IGNORECASE).strip()
        if not topic:
            return "Please specify what kind of message to draft. Say 'draft message [topic]'"
        return draft_message(topic)

    elif intent == "task_suggestion":
        # Extract task description
        task_desc = re.sub(r'.*suggest.*task\s+', '', command, flags=re.IGNORECASE).strip()
        if not task_desc:
            # Try to get from recent tasks
            tasks = get_tasks()
            if "No tasks found" not in tasks:
                return "Please specify which task you need suggestions for, or say 'suggest task [description]'"
            task_desc = "general productivity"  # fallback
        return generate_smart_suggestion(task_desc)

    elif intent == "draft_email":
        # Extract subject after "draft email"
        subject = re.sub(r'^draft\s+email\s+', '', command, flags=re.IGNORECASE).strip()
        if not subject:
            return "Please specify the email subject. Say 'draft email [subject]'"
        return draft_email(subject)

    elif intent == "smart_suggestions":
        suggestions = get_smart_suggestions()
        if not suggestions:
            return "No suggestions available yet. Keep using me to learn your patterns!"
        result = "🤖 Smart Suggestions based on your patterns:\n"
        for i, suggestion in enumerate(suggestions, 1):
            result += f"{i}. {suggestion}\n"
        result += "\nWould you like me to help with any of these?"
        return result.strip()

    elif intent == "update_priorities":
        result = update_task_priorities()
        log_usage("update_priorities", True)
        return result

    elif intent == "analyze_patterns":
        # This would show usage patterns and insights
        return "Pattern analysis feature coming soon! I learn from your usage to provide better suggestions."

    elif intent == "exit":
        return "exit"

    else:
        return "I'm still learning this command. Try saying 'add task', 'read my tasks', 'complete task [number]', 'open notepad', 'open browser', 'what time is it', 'ask ChatGPT [question]', or 'exit'."
