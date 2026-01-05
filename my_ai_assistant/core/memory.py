import json
import os
from datetime import datetime, timedelta

TASKS_FILE = "tasks.json"
PREFERENCES_FILE = "preferences.json"
USAGE_LOG_FILE = "usage_log.json"

def load_tasks():
    if os.path.exists(TASKS_FILE):
        with open(TASKS_FILE, 'r') as f:
            return json.load(f)
    return []

def save_tasks(tasks):
    with open(TASKS_FILE, 'w') as f:
        json.dump(tasks, f, indent=2)

def add_task(description):
    tasks = load_tasks()
    task_id = len(tasks) + 1
    priority = predict_task_priority(description)
    task = {
        "id": task_id,
        "description": description,
        "completed": False,
        "created_at": datetime.now().isoformat(),
        "priority": priority
    }
    tasks.append(task)
    save_tasks(tasks)
    priority_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority, "🟡")
    return f"Task added: {description} {priority_icon}"

def get_tasks():
    tasks = load_tasks()
    if not tasks:
        return "No tasks found."
    result = "Your tasks:\n"
    for task in tasks:
        status = "✓" if task["completed"] else "○"
        priority = task.get("priority", "medium")
        priority_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority, "🟡")
        result += f"{task['id']}. {status} {priority_icon} {task['description']}\n"
    return result.strip()

def complete_task(task_id):
    tasks = load_tasks()
    for task in tasks:
        if task["id"] == task_id:
            task["completed"] = True
            task["completed_at"] = datetime.now().isoformat()
            save_tasks(tasks)
            # Learn from completion patterns
            learn_from_completion(task)
            return f"Task {task_id} marked as completed."
    return f"Task {task_id} not found."

# Learning AI Functions
def load_preferences():
    if os.path.exists(PREFERENCES_FILE):
        with open(PREFERENCES_FILE, 'r') as f:
            return json.load(f)
    return {
        "favorite_commands": {},
        "usage_patterns": {},
        "task_categories": {},
        "preferred_times": {}
    }

def save_preferences(prefs):
    with open(PREFERENCES_FILE, 'w') as f:
        json.dump(prefs, f, indent=2)

def log_usage(command, success=True):
    """Log command usage for learning patterns"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "command": command,
        "success": success,
        "day_of_week": datetime.now().weekday(),
        "hour": datetime.now().hour
    }

    # Load existing log
    if os.path.exists(USAGE_LOG_FILE):
        with open(USAGE_LOG_FILE, 'r') as f:
            logs = json.load(f)
    else:
        logs = []

    logs.append(log_entry)

    # Keep only last 1000 entries to prevent file from growing too large
    if len(logs) > 1000:
        logs = logs[-1000:]

    with open(USAGE_LOG_FILE, 'w') as f:
        json.dump(logs, f, indent=2)

def learn_from_completion(task):
    """Learn from task completion patterns"""
    prefs = load_preferences()

    # Analyze completion time
    created_at = datetime.fromisoformat(task["created_at"])
    completed_at = datetime.fromisoformat(task["completed_at"])
    completion_time = completed_at - created_at

    # Categorize task based on keywords
    description = task["description"].lower()
    category = "general"
    if any(word in description for word in ["work", "meeting", "email", "call"]):
        category = "work"
    elif any(word in description for word in ["shopping", "buy", "purchase"]):
        category = "shopping"
    elif any(word in description for word in ["exercise", "gym", "run", "walk"]):
        category = "health"
    elif any(word in description for word in ["clean", "laundry", "cook"]):
        category = "household"

    # Update category preferences
    if category not in prefs["task_categories"]:
        prefs["task_categories"][category] = {"count": 0, "avg_completion_hours": 0}

    prefs["task_categories"][category]["count"] += 1
    # Update average completion time
    current_avg = prefs["task_categories"][category]["avg_completion_hours"]
    count = prefs["task_categories"][category]["count"]
    prefs["task_categories"][category]["avg_completion_hours"] = (
        (current_avg * (count - 1)) + completion_time.total_seconds() / 3600
    ) / count

    save_preferences(prefs)

def get_smart_suggestions():
    """Generate smart suggestions based on learned patterns"""
    prefs = load_preferences()
    suggestions = []

    # Suggest based on time patterns
    current_hour = datetime.now().hour
    current_day = datetime.now().weekday()

    # Morning suggestions
    if 6 <= current_hour <= 10:
        suggestions.append("Good morning! Would you like me to check your tasks for today?")

    # Evening suggestions
    elif 18 <= current_hour <= 22:
        suggestions.append("Evening time! Would you like me to help you plan tomorrow's tasks?")

    # Weekend patterns
    if current_day >= 5:  # Saturday = 5, Sunday = 6
        suggestions.append("It's the weekend! Would you like suggestions for leisure activities?")

    # Task category suggestions
    if prefs["task_categories"]:
        most_common_category = max(prefs["task_categories"], key=lambda x: prefs["task_categories"][x]["count"])
        suggestions.append(f"You frequently work on {most_common_category} tasks. Need help with that category?")

    return suggestions if suggestions else ["No smart suggestions available yet. Keep using Jarvis to improve suggestions!"]

def predict_task_priority(description):
    """Predict task priority based on learned patterns"""
    prefs = load_preferences()
    desc_lower = description.lower()

    # Check for urgent keywords
    urgent_words = ["urgent", "asap", "deadline", "important", "critical", "today"]
    if any(word in desc_lower for word in urgent_words):
        return "high"

    # Check task categories and their typical completion times
    for category, data in prefs["task_categories"].items():
        category_keywords = {
            "work": ["work", "meeting", "email", "project", "deadline"],
            "shopping": ["buy", "purchase", "shop", "grocery"],
            "health": ["exercise", "gym", "doctor", "health"],
            "household": ["clean", "laundry", "cook", "repair"]
        }

        if category in category_keywords:
            if any(word in desc_lower for word in category_keywords[category]):
                avg_time = data.get("avg_completion_hours", 24)
                if avg_time < 2:  # Quick tasks
                    return "low"
                elif avg_time > 48:  # Long tasks
                    return "high"
                else:
                    return "medium"

    return "medium"  # Default priority

def update_task_priorities():
    """Update existing task priorities based on learning"""
    tasks = load_tasks()
    updated = False

    for task in tasks:
        if not task.get("completed", False) and "priority" not in task:
            task["priority"] = predict_task_priority(task["description"])
            updated = True

    if updated:
        save_tasks(tasks)
        return "Task priorities updated based on your patterns!"
    return "All tasks already have priorities."

# Legacy memory functions for backward compatibility
memory = {}

def remember(key, value):
    memory[key] = value

def recall(key):
    return memory.get(key, None)
