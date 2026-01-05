#!/usr/bin/env python3
"""
Jarvis Learning AI Demo
Demonstrates the learning capabilities of the Jarvis AI assistant
"""

from core.memory import (
    add_task, get_tasks, complete_task, get_smart_suggestions,
    predict_task_priority, update_task_priorities, load_preferences
)
from datetime import datetime, timedelta
import time

def demo_learning_ai():
    print("🤖 Jarvis Learning AI Demo")
    print("=" * 50)

    # Demo 1: Task Priority Prediction
    print("\n1. 🎯 Task Priority Prediction")
    test_tasks = [
        "urgent meeting with boss",
        "buy groceries for dinner",
        "clean the house",
        "exercise at gym",
        "work on project deadline"
    ]

    for task in test_tasks:
        priority = predict_task_priority(task)
        priority_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority, "🟡")
        print(f"   '{task}' → {priority_icon} {priority}")

    # Demo 2: Adding and completing tasks to build learning data
    print("\n2. 📝 Building Learning Data")
    print("   Adding sample tasks...")

    task_ids = []
    task_ids.append(add_task("buy milk from store"))
    task_ids.append(add_task("schedule dentist appointment"))
    task_ids.append(add_task("finish work report"))
    task_ids.append(add_task("call mom"))

    print("   Tasks added. Now completing some to create patterns...")

    # Simulate completion times (in a real scenario, this would happen over time)
    time.sleep(0.1)  # Tiny delay to simulate time passing
    complete_task(1)  # Quick shopping task
    time.sleep(0.1)
    complete_task(3)  # Work task

    # Demo 3: Smart Suggestions
    print("\n3. 💡 Smart Suggestions")
    suggestions = get_smart_suggestions()
    for i, suggestion in enumerate(suggestions, 1):
        print(f"   {i}. {suggestion}")

    # Demo 4: Updated Priorities
    print("\n4. 🔄 Priority Updates")
    print("   Adding more tasks to see priority learning...")
    add_task("urgent client call")
    add_task("water the plants")

    result = update_task_priorities()
    print(f"   {result}")

    # Show current tasks with priorities
    print("\n5. 📋 Current Tasks with Learned Priorities")
    tasks_display = get_tasks()
    print(tasks_display)

    # Demo 6: Learning Data Summary
    print("\n6. 📊 Learning Data Summary")
    prefs = load_preferences()
    if prefs.get("task_categories"):
        print("   Task Categories Learned:")
        for category, data in prefs["task_categories"].items():
            count = data.get("count", 0)
            avg_time = data.get("avg_completion_hours", 0)
            print(".1f"   else:)
        print("   No learning data yet. Keep using Jarvis!")

    print("\n✅ Demo Complete!")
    print("💡 The more you use Jarvis, the smarter it gets!")
    print("   It learns your patterns, preferences, and task completion habits.")

if __name__ == "__main__":
    demo_learning_ai()