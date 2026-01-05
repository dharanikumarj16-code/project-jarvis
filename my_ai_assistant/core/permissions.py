import datetime
import os

LOG_FILE = "permissions.log"

def log_decision(action, decision):
    """Log permission decisions for transparency"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] Action: {action} | Decision: {decision}\n"

    with open(LOG_FILE, 'a') as f:
        f.write(log_entry)

def ask_permission(action):
    """
    Permission-handling function that:
    - Clearly explains the action to the user
    - Accepts yes/no confirmation
    - Logs the decision
    - Blocks execution if permission is denied
    """
    print(f"\n🤖 AI Assistant wants to: {action}")
    print("This action will be performed on your local system.")

    while True:
        choice = input("Allow this action? (yes/no): ").lower().strip()

        if choice in ['yes', 'y']:
            log_decision(action, "ALLOWED")
            print("✅ Permission granted\n")
            return True
        elif choice in ['no', 'n']:
            log_decision(action, "DENIED")
            print("❌ Permission denied\n")
            return False
        else:
            print("Please answer 'yes' or 'no'")

def get_permission_history():
    """View permission decision history"""
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            return f.read()
    return "No permission history found."
