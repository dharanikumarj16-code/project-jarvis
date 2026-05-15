import sys
import os
# Add project root to sys.path to fix ModuleNotFoundError
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.permissions import ask_permission, get_permission_history
from core.memory import add_task, get_tasks, complete_task, log_usage, get_smart_suggestions, update_task_priorities, predict_task_priority, get_learned_actions, add_learned_action
from core.shortcuts_manager import get_learned_shortcut, learn_new_shortcut
from integrations.chatgpt import ask_chatgpt, generate_task_summary, draft_message
from integrations.gemini import ask_gemini, generate_smart_suggestion, draft_email, analyze_image, parse_automation_command, summarize_web_content, chat_with_gemini, correct_speech_text
from integrations.xai import decide_intent
from integrations.web import search_web, extract_text_from_url
from integrations.reasoning import ask_jarvis_llm
from integrations.automation import execute_sequence as execute_os_sequence
from output.speech import speak
from core.hand import DeviceController
from core.eyes import VisionSystem
from core.scheduler import scheduler
from core.neural import NeuralBrain
from core.nlp import intent_recognizer
import webbrowser
import datetime
import time
import re
import difflib
import logging

DEBUG_MODE = os.getenv('JARVIS_DEBUG', 'false').lower() == 'true'

# Global System State
current_mode = "GENERAL"

# Initialize Hardware and Vision
sys_control = DeviceController()
vision = VisionSystem()
neural_brain = NeuralBrain()

# Intent Handler Registry (Dictionary Mapping)
INTENT_HANDLERS = {}

def register_handler(intent_name):
    """Decorator to register intent handlers"""
    def decorator(func):
        INTENT_HANDLERS[intent_name] = func
        return func
    return decorator

@register_handler("tell_time")
def handle_tell_time(args=None):
    current_time = datetime.datetime.now().strftime("%I:%M %p")
    return f"The current time is {current_time}"

@register_handler("tell_date")
def handle_tell_date(args=None):
    current_date = datetime.datetime.now().strftime("%B %d, %Y")
    return f"Today's date is {current_date}"

@register_handler("add_task")
def handle_add_task(args=None):
    # args can be None if called from simple classify_command
    task_desc = args.get("description") if args else None
    if not task_desc:
        # Fallback to current command if available, though handlers should ideally get args
        return "Please specify what task to add."
    result = add_task(task_desc)
    log_usage("add_task", True)
    return result

@register_handler("read_tasks")
def handle_read_tasks(args=None):
    return get_tasks()

@register_handler("open_notepad")
def handle_open_notepad(args=None):
    if ask_permission("open Notepad"):
        os.system("start notepad")
        return "Notepad opened successfully"
    return "Permission denied."

@register_handler("open_browser")
def handle_open_browser(args=None):
    if ask_permission("open web browser"):
        webbrowser.open("https://google.com")
        return "Browser opened successfully"
    return "Permission denied."

@register_handler("open_calculator")
def handle_open_calculator(args=None):
    if ask_permission("open Calculator"):
        os.system("start calc")
        return "Calculator opened successfully"
    return "Permission denied."

# ... more handlers can be moved here for better structure

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
    original_command = command.strip()
    command = command.lower().strip()

    # 0. Neural Network Check (High Confidence)
    if neural_brain.ready:
        tag, confidence = neural_brain.predict(original_command)
        if confidence > 0.85: # 85% confidence threshold
            debug_log(f"🧠 Neural Net predicted: '{tag}' ({confidence:.2f})", 'info')
            return tag

    # Chat Mode
    if command in ["chat mode", "chat with gemini", "let's chat", "talk to me"]:
        debug_log("Classified as: enter_chat_mode", 'debug')
        return "enter_chat_mode"

    # Learning Actions (Teacher Mode)
    if command.startswith("learn action") or command.startswith("teach me to"):
        debug_log("Classified as: learn_action", 'debug')
        return "learn_action"
        
    # Check for Learned Actions (Exact match, high priority)
    learned_actions = get_learned_actions()
    clean_cmd = command.replace("execute ", "").strip()
    if clean_cmd in learned_actions:
        debug_log(f"Classified as: execute_learned_action ({clean_cmd})", 'debug')
        return "execute_learned_action"

    # Automation Chain (starts with "do" or contains sequence keywords)
    if command.startswith("do ") or (" and " in command and ("open" in command or "click" in command)):
        debug_log("Classified as: automation_chain", 'debug')
        return "automation_chain"

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
    # File/Folder opener
    if command.startswith("open file") or command.startswith("open folder") or command.startswith("play "):
        debug_log("Classified as: open_file_folder", 'debug')
        return "open_file_folder"

    # Create File/Folder
    if command.startswith("create file") or command.startswith("create folder") or command.startswith("new file") or command.startswith("new folder"):
        debug_log("Classified as: create_file_folder", 'debug')
        return "create_file_folder"

    # Direct path check
    if os.path.exists(original_command) or os.path.exists(original_command.strip('"\'')):
        debug_log("Classified as: open_file_folder (direct path)", 'debug')
        return "open_file_folder"

    # Research / Web Reading
    if "research" in command or "read website" in command or "find info about" in command:
        debug_log("Classified as: research_topic", 'debug')
        return "research_topic"

    # Web search commands
    if "search for" in command or "search about" in command or "google" in command:
        debug_log("Classified as: search_web", 'debug')
        return "search_web"

    # WhatsApp & Messaging commands (more specific first)
    if "type and send" in command:
        debug_log("Classified as: whatsapp_type_and_send", 'debug')
        return "whatsapp_type_and_send"
    if "clear text" in command:
        return "whatsapp_clear_text"
    if "add new line" in command or "new line" in command:
        return "whatsapp_add_new_line"
    if "attach" in command or "send file" in command:
        debug_log("Classified as: whatsapp_attach_file", 'debug')
        return "whatsapp_attach_file"
    if "send message" in command or ("send" in command and "whatsapp" in command):
        debug_log("Classified as: whatsapp_send_message", 'debug')
        return "whatsapp_send_message"
    if "open chat" in command or "open whatsapp" in command:
        debug_log("Classified as: whatsapp_open_chat", 'debug')
        return "whatsapp_open_chat"

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
        
    # System Application Control (Specific apps)
    if "open notepad" in command:
        debug_log("Classified as: open_notepad", 'debug')
        return "open_notepad"
    if "open browser" in command or "open chrome" in command:
        debug_log("Classified as: open_browser", 'debug')
        return "open_browser"
    if "open calculator" in command:
        debug_log("Classified as: open_calculator", 'debug')
        return "open_calculator"

    # List files in folder
    if command.startswith("list files") or command.startswith("show files") or command.startswith("list folder"):
        debug_log("Classified as: list_files", 'debug')
        return "list_files"

    # Device Control Commands (Mouse/Keyboard)
    if "take a screenshot" in command or "capture screen" in command:
        return "take_screenshot"
    if "start screen recording" in command or "record screen" in command or "stop screen recording" in command:
        return "screen_record"
    if command.startswith("type ") or command.startswith("write "):
        debug_log("Classified as: type_text", 'debug')
        return "type_text"
    if "scroll up" in command:
        return "scroll_up"
    if "scroll down" in command:
        return "scroll_down"
    if "right click" in command:
        return "right_click"
    if "click" in command:
        return "click_mouse"
    if "press enter" in command:
        return "press_enter"
    if "copy all" in command or "select all" in command:
        return "system_select_all"
    if "copy" in command:
        return "system_copy"
    if "paste" in command:
        return "system_paste"
    if "cut" in command:
        return "system_cut"
    if "close tab" in command:
        return "system_close_tab"
    if "minimize" in command or "immizise" in command:
        return "system_minimize"
    if "open new" in command:
        return "system_new_tab"
    if "show desktop" in command or "desktop" in command or "destop" in command:
        return "system_show_desktop"
    if "home page" in command or "go home" in command:
        return "system_go_home"
    if command.startswith("do shortcut") or command.startswith("shortcut"):
        return "do_shortcut"

    if "what do you see" in command or "take a photo" in command or "look" in command:
        return "vision_analyze"
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
        
    # Scheduler Commands
    if "silent mode" in command:
        debug_log("Classified as: set_silent_mode", 'debug')
        return "set_silent_mode"
    if "alarm" in command or "timer" in command:
        debug_log("Classified as: set_alarm", 'debug')
        return "set_alarm"

    # Check for Learned Actions
    learned_actions = get_learned_actions()
    clean_cmd = command.replace("execute ", "").strip()
    if clean_cmd in learned_actions:
        debug_log(f"Classified as: execute_learned_action ({clean_cmd})", 'debug')
        return "execute_learned_action"

    # OS Reasoning Engine Commands
    if "anti gravity" in command or command.startswith("find ") or "click on" in command or "type into" in command or command.startswith("scroll ") or command.startswith("drag ") or command.startswith("move "):
        debug_log("Classified as: os_reasoning", 'debug')
        return "os_reasoning"

    # --- AGENTIC FALLBACK: Fuzzy Matching ---
    # This handles voice mistakes locally (e.g., "open no pad" -> "open notepad")
    # without asking Gemini.
    
    known_commands = {
        "open notepad": "open_notepad",
        "open no pad": "open_notepad",
        "open note pad": "open_notepad",
        "run notepad": "open_notepad",
        
        "open calculator": "open_calculator",
        "open calc": "open_calculator",
        
        "open browser": "open_browser",
        "open chrome": "open_browser",
        "open google": "open_browser",
        "open internet": "open_browser",
        
        "read my tasks": "read_tasks",
        "show tasks": "read_tasks",
        "list tasks": "read_tasks",
        "my tasks": "read_tasks",
        
        "what time is it": "tell_time",
        "current time": "tell_time",
        "what date is it": "tell_date",
        "today's date": "tell_date",
        "permission history": "permission_history",
        "show permissions": "permission_history"
    }
    
    # Find closest match if confidence is high (> 0.6)
    matches = difflib.get_close_matches(command, known_commands.keys(), n=1, cutoff=0.6)
    if matches:
        debug_log(f"🧩 Fuzzy match: '{command}' -> '{matches[0]}'", 'debug')
        return known_commands[matches[0]]

    debug_log("Classified as: unknown", 'debug')
    return "unknown"

def execute_automation_steps(steps):
    """Helper to execute a list of automation steps with Fail-safe preview"""
    
    # Fail-safe: Visual confirmation (Preview)
    print("\n📋 AUTOMATION PREVIEW:")
    for i, step in enumerate(steps, 1):
        print(f"   {i}. {step.get('action').upper()}: {step.get('value')}")
        
    if not ask_permission("execute this automation sequence", risk_level="high"):
        return ["❌ Automation cancelled."]

    results = []
    for step in steps:
        action = step.get("action")
        value = step.get("value")
        
        try:
            if action == "open":
                # Basic app mapping
                app_map = {"whatsapp": "whatsapp:", "chrome": "chrome", "notepad": "notepad", "calculator": "calc"}
                target = app_map.get(str(value).lower(), str(value))
                os.system(f'start "" "{target}"')
                results.append(f"Opened {value}")
                
            elif action == "type":
                sys_control.type_text(str(value))
                results.append(f"Typed '{value}'")
                
            elif action == "press":
                sys_control.press_key(str(value))
                results.append(f"Pressed {value}")
                
            elif action == "click":
                sys_control.click(str(value))
                results.append("Clicked mouse")
                
            elif action == "wait":
                time.sleep(float(value))
                
        except Exception as e:
            results.append(f"Error on {action}: {e}")
    return results

def parse_time_string(text):
    """Helper to extract time from string (e.g. '9 am', '14:30')"""
    match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', text.lower())
    if not match: return None
    
    h = int(match.group(1))
    m = int(match.group(2) or 0)
    ampm = match.group(3)
    
    if ampm:
        if ampm == 'pm' and h < 12: h += 12
        if ampm == 'am' and h == 12: h = 0
    return datetime.time(h, m)

def process_request(user_input, mode=None):
    """
    High-level entry point for processing requests with explicit mode awareness.
    As recommended by the Senior AI Engineer prompt.
    """
    global current_mode
    if mode:
        current_mode = mode
        
    return process_command(user_input)

def process_command(command):
    """
    Agentic Pipeline:
    User -> Intent Filter -> NLP Mode Guard -> Agent Brain -> Planner -> Validator -> Executor -> Memory
    """
    global current_mode
    
    # --- 0. NLP Mode Guard & Switch Logic ---
    if "switch to" in command.lower() and "mode" in command.lower():
        new_mode = command.lower().replace("switch to", "").replace("mode", "").strip().upper().replace(" ", "_")
        if new_mode:
            current_mode = new_mode
            return f"Switched to {current_mode.replace('_', ' ').title()}."

    # Analyze intent using spaCy NLP
    intent_tag, target_mode = intent_recognizer.extract_intent(command)
    
    # Validation Logic: Mode Awareness
    if target_mode and target_mode != current_mode and current_mode != "GENERAL":
        return f"I detected a {intent_tag.lower()} command, but I am in {current_mode.replace('_', ' ').title()}. Should I switch to {target_mode.replace('_', ' ').title()}?"

    # --- 1. Intent Filter (MiniLM / NeuralBrain / Regex) ---
    if command.lower() in ["exit", "quit", "stop", "bye"]:
        return "exit"

    intent = classify_command(command)
    args = {}
    
    if intent == "unknown":
        debug_log("Local classification failed. Attempting Gemini speech correction...", 'info')
        
        # A. Try Speech Correction (Fast Brain)
        try:
            corrected = correct_speech_text(command)
            # Ensure we got a valid correction (not an error message or empty)
            if corrected and "Error" not in corrected and corrected.lower() != command.lower():
                debug_log(f"Gemini corrected: '{command}' -> '{corrected}'", 'info')
                command = corrected
                intent = classify_command(command)
        except Exception as e:
            debug_log(f"Gemini speech correction failed: {str(e)}", 'error')
            
        # B. Full Agentic Decision (Slow Brain)
        if intent == "unknown":
            brain_result = decide_intent(command)
            brain_intent = brain_result.get("intent")
            
            if brain_intent and brain_intent != "error":
                if brain_intent == "chat":
                    return brain_result.get("response_text")
                
                # Map Brain Intent to Local Intent
                intent = brain_intent
                args = brain_result.get("args", {})
                debug_log(f"Agent Brain decided: {intent} with args {args}", 'info')
            
    debug_log(f"Intent classified as: {intent}", 'info')

    # --- 2. Dispatch to Registered Handlers ---
    if intent in INTENT_HANDLERS:
        return INTENT_HANDLERS[intent](args)

    # --- 3. Planner, 4. Validator, 5. Executor ---

    if intent == "os_reasoning":
        if ask_permission(f"execute OS reasoning for '{command}'"):
            speak("Scanning screen and thinking...")
            ocr_data = vision.get_ocr_data()
            commands_sequence = ask_jarvis_llm(command, ocr_data)
            if commands_sequence:
                success = execute_os_sequence(commands_sequence)
                return "OS reasoning execution complete." if success else "OS reasoning encountered an error."
            else:
                return "Could not formulate an OS reasoning plan."
        return "Permission denied."

    if intent == "add_task":
        task_desc = args.get("description")
        if not task_desc:
            task_desc = re.sub(r'^add task\s*', '', command, flags=re.IGNORECASE).strip()

        if not task_desc:
            return "Please specify what task to add. Say 'add task [description]'"
        result = add_task(task_desc)
        log_usage("add_task", True)
        return result

    elif intent == "read_tasks":
        return get_tasks()

    elif intent == "complete_task":
        task_id = args.get("task_id")
        if not task_id:
            match = re.search(r'(\d+)', command)
            if match: task_id = int(match.group(1))

        if task_id:
            return complete_task(int(task_id))
        return "Please specify which task number to complete."

    elif intent == "open_notepad":
        if ask_permission("open Notepad"):
            os.system("start notepad")
            return "Notepad opened successfully"
        return "Permission denied."

    elif intent == "open_browser":
        if ask_permission("open web browser"):
            webbrowser.open("https://google.com")
            return "Browser opened successfully"
        return "Permission denied."

    elif intent == "open_calculator":
        if ask_permission("open Calculator"):
            os.system("start calc")
            return "Calculator opened successfully"
        return "Permission denied."

    elif intent == "list_files":
        target = re.sub(r'^(list files|show files|list folder)(\s+in)?\s+', '', command, flags=re.IGNORECASE).strip()
        if not target:
            return "Which folder should I list?"
            
        # Common user directories to search
        user_home = os.path.expanduser("~")
        search_dirs = [
            user_home,
            os.path.join(user_home, "Desktop"),
            os.path.join(user_home, "Documents"),
            os.path.join(user_home, "Downloads"),
            os.path.join(user_home, "Pictures"),
            os.path.join(user_home, "Videos"),
            os.path.join(user_home, "Music")
        ]
        
        found_path = None
        
        # Check if full path
        if os.path.exists(target) and os.path.isdir(target):
            found_path = target
        else:
            # Search common dirs
            for directory in search_dirs:
                if not os.path.exists(directory): continue
                
                potential_path = os.path.join(directory, target)
                if os.path.exists(potential_path) and os.path.isdir(potential_path):
                    found_path = potential_path
                    break
                    
                try:
                    for item in os.listdir(directory):
                        if item.lower() == target.lower():
                            full_path = os.path.join(directory, item)
                            if os.path.isdir(full_path):
                                found_path = full_path
                                break
                except PermissionError:
                    continue
                if found_path: break
                
        if found_path:
            if ask_permission(f"list files in {found_path}"):
                try:
                    items = os.listdir(found_path)
                    if not items:
                        return f"Folder '{os.path.basename(found_path)}' is empty."
                    
                    # Separate folders and files for nicer output
                    folders = [f"📁 {i}" for i in items if os.path.isdir(os.path.join(found_path, i))]
                    files = [f"📄 {i}" for i in items if os.path.isfile(os.path.join(found_path, i))]
                    
                    all_items = folders + files
                    count = len(all_items)
                    
                    display_items = "\n".join(all_items[:15])
                    if count > 15:
                        display_items += f"\n... and {count - 15} more items."
                        
                    return f"Contents of {os.path.basename(found_path)} ({count} items):\n{display_items}"
                except Exception as e:
                    return f"Error listing folder: {str(e)}"
            return "Permission denied."
        else:
            return f"Folder '{target}' not found."

    elif intent == "open_file_folder":
        target = re.sub(r'^(open (file|folder)|play)\s+', '', command, flags=re.IGNORECASE).strip()
        target = target.strip('"\'')  # Remove quotes if present
        if not target:
            return "What file or folder should I open?"
            
        # Common user directories to search
        user_home = os.path.expanduser("~")
        search_dirs = [
            user_home,
            os.path.join(user_home, "Desktop"),
            os.path.join(user_home, "Documents"),
            os.path.join(user_home, "Downloads"),
            os.path.join(user_home, "Pictures"),
            os.path.join(user_home, "Videos"),
            os.path.join(user_home, "Music")
        ]
        
        found_path = None
        
        # Prepare search candidates
        candidates = [target]
        
        # Handle "filename extension" pattern (e.g., "report ppt" -> "report.ppt")
        parts = target.split()
        if len(parts) > 1:
            name_part = " ".join(parts[:-1])
            # Clean extension of parens if present, e.g. "(ppt)" -> "ppt"
            ext_part = parts[-1].replace('(', '').replace(')', '')
            candidates.append(f"{name_part}.{ext_part}")
        
        # 1. Check if it's a full path
        if os.path.exists(target):
            found_path = target
        else:
            # 2. Search in common directories
            print(f"🔍 Searching for '{target}'...")
            for directory in search_dirs:
                if not os.path.exists(directory): continue
                
                for candidate in candidates:
                    # Check exact match first
                    potential_path = os.path.join(directory, candidate)
                    if os.path.exists(potential_path):
                        found_path = potential_path
                        break
                        
                    # Case-insensitive search
                    try:
                        for item in os.listdir(directory):
                            if item.lower() == candidate.lower():
                                found_path = os.path.join(directory, item)
                                break
                    except PermissionError:
                        continue
                    if found_path: break
                if found_path: break
        
        if found_path:
            if ask_permission(f"open {found_path}"):
                try:
                    if hasattr(os, 'startfile'):
                        os.startfile(found_path)
                    else:
                        os.system(f'start "" "{found_path}"')
                    return f"Opened: {found_path}"
                except Exception as e:
                    return f"Error opening {target}: {str(e)}"
            return "Permission denied."
        else:
            return f"Could not find file or folder named '{target}' in common directories."

    elif intent == "create_file_folder":
        # Pattern: "create folder [name]" or "new file [name]"
        match = re.search(r'^(create|new)\s+(file|folder)\s+(.+)', command, flags=re.IGNORECASE)
        if not match:
            return "Please specify what to create. Say 'create folder [name]' or 'create file [name]'."
            
        item_type = match.group(2).lower()
        name = match.group(3).strip()
        
        # Default to Desktop for easy access
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        target_path = os.path.join(desktop, name)
        
        if ask_permission(f"create {item_type} '{name}' on Desktop"):
            try:
                if item_type == "folder":
                    os.makedirs(target_path, exist_ok=True)
                    return f"Folder created on Desktop: {name}"
                else:
                    # Create empty file
                    with open(target_path, 'w') as f:
                        pass
                    return f"File created on Desktop: {name}"
            except Exception as e:
                return f"Error creating {item_type}: {str(e)}"
        return "Permission denied."

    elif intent == "open_general":
        app_name = re.sub(r'^open\s+', '', command, flags=re.IGNORECASE).strip()
        if not app_name:
            app_name = re.sub(r'^open\s+', '', command, flags=re.IGNORECASE).strip()
            
        if not app_name:
            return "Please specify an application to open."
            
        # Enhanced mapping for common Windows applications
        app_map = {
            "calculator": "calc",
            "notepad": "notepad",
            "paint": "mspaint",
            "cmd": "cmd",
            "command prompt": "cmd",
            "terminal": "wt",
            "powershell": "powershell",
            "explorer": "explorer",
            "file explorer": "explorer",
            "this pc": "explorer",
            "my computer": "explorer",
            "chrome": "chrome",
            "google chrome": "chrome",
            "edge": "msedge",
            "word": "winword",
            "excel": "excel",
            "powerpoint": "powerpnt",
            "settings": "ms-settings:",
            "whatsapp": "whatsapp:",
            "spotify": "spotify:"
        }
        
        # 1. Check if it's a mapped app
        target = app_map.get(app_name.lower())
        
        if target:
            if ask_permission(f"open {app_name}"):
                try:
                    os.system(f'start "" "{target}"')
                    return f"Opening {app_name}"
                except Exception as e:
                    return f"Error opening {app_name}: {str(e)}"
            return "Permission denied."

        # 2. If not mapped, try to find it as a file or folder
        user_home = os.path.expanduser("~")
        search_dirs = [
            user_home,
            os.path.join(user_home, "Desktop"),
            os.path.join(user_home, "Documents"),
            os.path.join(user_home, "Downloads"),
            os.path.join(user_home, "Pictures"),
            os.path.join(user_home, "Videos"),
            os.path.join(user_home, "Music")
        ]
        
        found_path = None
        if os.path.exists(app_name):
            found_path = app_name
        else:
            for directory in search_dirs:
                if not os.path.exists(directory): continue
                
                # Check exact match
                potential = os.path.join(directory, app_name)
                if os.path.exists(potential):
                    found_path = potential
                    break
                    
                # Check case-insensitive
                try:
                    for item in os.listdir(directory):
                        if item.lower() == app_name.lower():
                            found_path = os.path.join(directory, item)
                            break
                except: continue
                if found_path: break
        
        if found_path:
            if ask_permission(f"open {found_path}"):
                try:
                    if hasattr(os, 'startfile'):
                        os.startfile(found_path)
                    else:
                        os.system(f'start "" "{found_path}"')
                    return f"Opened: {found_path}"
                except Exception as e:
                    return f"Error opening {found_path}: {str(e)}"
            return "Permission denied."

        # 3. Fallback: Try to run it as a command
        if ask_permission(f"open {app_name}"):
            try:
                os.system(f'start "" "{app_name}"')
                return f"Attempting to open {app_name}"
            except Exception as e:
                return f"Error opening {app_name}: {str(e)}"
        return "Permission denied."

    elif intent == "research_topic":
        topic = args.get("topic")
        if not topic:
            topic = re.sub(r'^(research|find info about|read website)\s+', '', command, flags=re.IGNORECASE).strip()
        if not topic:
            return "What should I research?"
        if ask_permission(f"search the web and read content about '{topic}'"):
            speak(f"Searching for {topic}")
            results = search_web(topic)
            if not results:
                return "I couldn't find any results on the web."
            best_url = results[0]['href']
            print(f"🌐 Reading: {results[0]['title']} ({best_url})")
            speak(f"Reading {results[0]['title']}")
            content = extract_text_from_url(best_url)
            summary = summarize_web_content(topic, content)
            return f"Here is what I found from {results[0]['title']}:\n\n{summary}"
        return "Research cancelled."

    elif intent == "search_web":
        query = re.sub(r'^(search\s+(for|about)|google)\s+', '', command, flags=re.IGNORECASE).strip()
        query = args.get("query")
        if not query:
            return "Please specify what to search for. Say 'Jarvis search for [topic]'"
        if ask_permission(f"search Google for '{query}'"):
            webbrowser.open(f"https://www.google.com/search?q={query}")
            return f"Searching Google for {query}"
        return "Search cancelled."

    elif intent == "tell_time":
        current_time = datetime.datetime.now().strftime("%I:%M %p")
        return f"The current time is {current_time}"

    elif intent == "tell_date":
        current_date = datetime.datetime.now().strftime("%B %d, %Y")
        return f"Today's date is {current_date}"

    elif intent == "permission_history":
        return get_permission_history()

    elif intent == "gemini_query":
        query = re.sub(r'^(ask|use)\s+gemini\s+', '', command, flags=re.IGNORECASE).strip()
        return ask_gemini(query)

    elif intent == "chatgpt_query":
        query = re.sub(r'^(ask|use)\s+chatgpt\s+', '', command, flags=re.IGNORECASE).strip()
        return ask_chatgpt(query)

    elif intent == "enter_chat_mode":
        speak("Entering chat mode. Say exit to leave.")
        print("💬 Chat Mode Active (Say 'exit' to quit)")
        from input.voice import listen
        chat_with_gemini("", reset=True)
        while True:
            q = listen()
            if not q: continue
            if "exit" in q.lower() or "stop" in q.lower():
                return "Exiting chat mode."
            response = chat_with_gemini(q)
            print(f"Gemini: {response}")
            speak(response)
            
            # Check if it's a command first
            sub_intent = classify_command(q)
            if sub_intent != "unknown" and sub_intent != "enter_chat_mode":
                # Execute command inside chat mode
                result = process_command(q)
                print(f"Jarvis: {result}")
                speak(result)
            else:
                # Fallback to Chat
                response = chat_with_gemini(q)
                print(f"Gemini: {response}")
                speak(response)

    elif intent == "vision_analyze":
        if ask_permission("access the camera"):
            image_path = vision.capture_image()
            if image_path:
                return analyze_image("Describe what you see in this image in detail.", image_path)
            return "Failed to capture image."
        return "Camera access denied."

    elif intent == "learn_action":
        name = args.get("action_name")
        if not name:
            name = re.sub(r'^(learn action|teach me to)\s+', '', command).strip()
        
        if not name:
            return "What action should I learn? Say 'learn action [name]'"
        
        speak(f"What steps should I perform for {name}?")
        print(f"🤔 Listening for steps for '{name}'...")
        
        # Import listen locally
        from input.voice import listen
        steps_desc = listen()
        
        if not steps_desc:
            return "I didn't hear any steps. Action learning cancelled."
            
        speak("Analyzing steps...")
        steps = parse_automation_command(steps_desc)
        
        if not steps:
            return "I couldn't understand those steps."
            
        return add_learned_action(name, steps)
    
    elif intent == "execute_learned_action" or intent == "execute_action":
        clean_cmd = args.get("action_name")
        if not clean_cmd:
            clean_cmd = command.replace("execute ", "").strip()
            
        steps = get_learned_actions().get(clean_cmd)
        
        if not steps:
            return f"Action '{clean_cmd}' not found."
            
        if ask_permission(f"execute learned action '{clean_cmd}'"):
            results = execute_automation_steps(steps)
            return f"Action '{clean_cmd}' completed."
        return "Action cancelled."

    elif intent == "smart_suggestions":
        suggestions = get_smart_suggestions()
        return "\n".join(suggestions)

    elif intent == "update_priorities":
        return update_task_priorities()

    elif intent == "task_summary":
        return generate_task_summary(get_tasks())

    elif intent == "draft_message":
        topic = re.sub(r'^draft\s+message\s+', '', command, flags=re.IGNORECASE).strip()
        return draft_message(topic)

    elif intent == "draft_email":
        subject = re.sub(r'^draft\s+email\s+', '', command, flags=re.IGNORECASE).strip()
        return draft_email(subject)

    elif intent == "whatsapp_open_chat":
        # Extract target name: "open chat Kavi" -> "Kavi"
        target = re.sub(r'^.*?(open chat|open whatsapp|chat with)\s*', '', command, flags=re.IGNORECASE).strip()

        # If just "open whatsapp", open the app
        if not target or target.lower() == "whatsapp":
            if ask_permission("open WhatsApp"):
                os.system('start "" "whatsapp:"')
                return "WhatsApp opened."
            else:
                return "Permission denied."

        # Otherwise, open a specific chat
        else:
            if ask_permission(f"open WhatsApp chat with {target}"):
                speak(f"Opening chat with {target}")
                os.system('start "" "whatsapp:"')
                time.sleep(1.5) # Wait for app to focus

                # Use Ctrl + N to open 'New Chat' picker (Reliable for finding contacts)
                sys_control.hotkey('ctrl', 'n')
                time.sleep(0.5)

                sys_control.type_text(target)
                time.sleep(1.0) # Wait for search results

                sys_control.press_key('enter') # Select top result
                return f"Chat with {target} opened."
            return "Permission denied."

    elif intent == "type_text":
        text = re.sub(r'^(type|write)\s+', '', command, flags=re.IGNORECASE).strip()
        if ask_permission(f"type text: '{text}'"):
            sys_control.type_text(text)
            return "Text typed."
        return "Permission denied."

    elif intent == "whatsapp_type_and_send":
        text = re.sub(r'^type and send\s+', '', command, flags=re.IGNORECASE).strip()
        if ask_permission(f"type and send: '{text}'"):
            sys_control.type_text(text)
            time.sleep(0.5)
            sys_control.press_key('enter')
            return "Message sent."
        return "Permission denied."

    elif intent == "whatsapp_clear_text":
        if ask_permission("clear text"):
            sys_control.hotkey('ctrl', 'a')
            time.sleep(0.1)
            sys_control.press_key('backspace')
            return "Text cleared."
        return "Permission denied."

    elif intent == "whatsapp_add_new_line":
        if ask_permission("add new line"):
            sys_control.hotkey('shift', 'enter')
            return "New line added."
        return "Permission denied."

    elif intent == "whatsapp_attach_file":
        target = re.sub(r'^(attach|send file)\s*', '', command, flags=re.IGNORECASE).strip()
        
        # Generic attach (opens dialog)
        if not target or target.lower() in ["image", "photo", "file", "document"]:
            if ask_permission("open attachment picker"):
                sys_control.hotkey('ctrl', 'shift', 'u')
                return "Attachment picker opened."
            return "Permission denied."
            
        # Specific file search
        target = target.replace(" dot ", ".").replace(" point ", ".")
        user_home = os.path.expanduser("~")
        search_dirs = [
            os.path.join(user_home, "Downloads"),
            os.path.join(user_home, "Documents"),
            os.path.join(user_home, "Desktop"),
            os.path.join(user_home, "Pictures")
        ]
        
        found_path = None
        for directory in search_dirs:
            if not os.path.exists(directory): continue
            potential = os.path.join(directory, target)
            if os.path.exists(potential):
                found_path = potential
                break
        
        if found_path:
            if ask_permission(f"attach file: {os.path.basename(found_path)}"):
                sys_control.hotkey('ctrl', 'shift', 'u')
                time.sleep(1.0) # Wait for dialog
                sys_control.type_text(found_path)
                time.sleep(0.5)
                sys_control.press_key('enter')
                return f"Attached {os.path.basename(found_path)}"
            return "Permission denied."
        return f"Could not find file '{target}' to attach."

    elif intent == "whatsapp_send_message":
        # Atomic step: Press Enter to send
        if ask_permission("send the current message"):
            sys_control.press_key('enter')
            return "Message sent."
        return "Permission denied."

    elif intent == "task_suggestion":
        task_desc = re.sub(r'.*suggest.*task\s+', '', command, flags=re.IGNORECASE).strip()
        return generate_smart_suggestion(task_desc)

    # --- System Control Dispatcher ---
    # Groups simple device control commands for cleaner logic
    sys_actions = {
        "scroll_up": lambda: sys_control.scroll("up"),
        "scroll_down": lambda: sys_control.scroll("down"),
        "click_mouse": lambda: sys_control.click("left"),
        "right_click": lambda: sys_control.click("right"),
        "press_enter": lambda: sys_control.press_key("enter"),
        "system_copy": lambda: sys_control.hotkey("ctrl", "c"),
        "system_paste": lambda: sys_control.hotkey("ctrl", "v"),
        "system_cut": lambda: sys_control.hotkey("ctrl", "x"),
        "system_select_all": lambda: sys_control.hotkey("ctrl", "a"),
        "system_close_tab": lambda: sys_control.hotkey("ctrl", "w"),
        "system_minimize": lambda: sys_control.hotkey("win", "down"),
        "system_new_tab": lambda: sys_control.hotkey("ctrl", "t"),
        "system_show_desktop": lambda: sys_control.hotkey("win", "d"),
        "system_go_home": lambda: sys_control.hotkey("alt", "home"),
        "take_screenshot": lambda: sys_control.hotkey("win", "shift", "s"),
        "screen_record": lambda: sys_control.hotkey("win", "alt", "r")
    }
    
    if intent in sys_actions:
        return sys_actions[intent]()

    elif intent == "do_shortcut":
        keys_raw = re.sub(r'^(do\s+)?shortcut\s+', '', command, flags=re.IGNORECASE).strip()
        if not keys_raw: return "Please specify keys for the shortcut."
        
        # Check if user spoke explicit keys (e.g. "ctrl plus c") or an action (e.g. "copy")
        explicit_keywords = [
            'ctrl', 'alt', 'shift', 'win', 'enter', 'tab', 'delete', 'esc', 
            'space', 'backspace', 'up', 'down', 'left', 'right', 'home', 'end', 
            'insert', 'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12'
        ]
        is_explicit = any(k in keys_raw.lower() for k in explicit_keywords)
        
        final_keys = []
        
        if is_explicit:
            # Explicit keys logic
            keys = re.split(r'\s+(?:plus|and)\s+|\s+', keys_raw)
            keys = [k.strip().lower() for k in keys if k.strip()]
            key_map = {"control": "ctrl", "escape": "esc", "delete": "delete", "insert": "insert", "windows": "win"}
            final_keys = [key_map.get(k, k) for k in keys]
        else:
            # Action Learning Logic
            action = keys_raw
            learned_keys = get_learned_shortcut(action)
            
            if not learned_keys:
                speak(f"I don't know the shortcut for {action}. Searching online...")
                learned_keys = learn_new_shortcut(action)
                
            if learned_keys:
                final_keys = learned_keys.split('+')
            else:
                return f"Could not find a shortcut for {action}."

        if final_keys:
            if ask_permission(f"press shortcut keys: {' + '.join(final_keys)}"):
                sys_control.hotkey(*final_keys)
                return f"Executed shortcut: {'+'.join(final_keys)}"
            return "Permission denied."

    elif intent == "automation_chain":
        clean_command = re.sub(r'^do\s+', '', command, flags=re.IGNORECASE).strip()
        steps = parse_automation_command(clean_command)
        if steps and ask_permission(f"execute automation: {clean_command}"):
            execute_automation_steps(steps)
            return "Automation complete."
        return "Automation failed."
        
    elif intent == "set_alarm":
        # Handle "set timer for 10 minutes"
        if "timer" in command:
            minutes = re.search(r'(\d+)\s*min', command)
            if minutes:
                mins = int(minutes.group(1))
                target = datetime.datetime.now() + datetime.timedelta(minutes=mins)
                return scheduler.add_alarm(target, "Timer")
            return "How many minutes for the timer?"
            
        # Handle "set alarm for 9 am"
        time_obj = parse_time_string(command)
        if time_obj:
            now = datetime.datetime.now()
            target = now.replace(hour=time_obj.hour, minute=time_obj.minute, second=0)
            if target <= now:
                target += datetime.timedelta(days=1) # Set for tomorrow if time passed
            return scheduler.add_alarm(target, "Alarm")
        return "I couldn't understand the time. Please say 'set alarm for 9 am'."

    elif intent == "set_silent_mode":
        # Format: "silent mode tomorrow 9 am to 5 pm" or "silent mode every day..."
        
        # 1. Extract times
        parts = command.split(" to ")
        if len(parts) < 2:
            return "Please specify a start and end time. E.g., 'silent mode 9am to 5pm'."
        start_part = parts[0].replace("silent mode", "").strip()
        end_part = parts[1].strip()
        start_time = parse_time_string(start_part)
        end_time = parse_time_string(end_part)
        
        if not start_time or not end_time:
            return  "I couldn't understand the times. Please say 'silent mode 9 am to 5 pm'."   
