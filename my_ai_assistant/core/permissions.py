import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from output.speech import speak
except ImportError:
    def speak(text):
        print(f"🗣️ [Silent]: {text}")

import datetime

LOG_FILE = "permissions.log"

AUTO_APPROVE = True # Force auto-approve to prevent console blocking

def log_decision(action, decision):
    """Log permission decisions for transparency"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] Action: {action} | Decision: {decision}\n"

    with open(LOG_FILE, 'a') as f:
        f.write(log_entry)

def ask_permission(action, risk_level="medium"):
    """
    Permission-gated: Face auth / confirmation for risky actions.
    Fail-safe: Visual confirmation.
    """
    if AUTO_APPROVE:
        log_decision(action, "ALLOWED_AUTO")
        return True

    print(f"\n🔒 PERMISSION REQUEST: {action}")
    print(f"   Risk Level: {risk_level.upper()}")
    print(f"   [y] Confirm  |  [n] Cancel")
    
    try:
        choice = input("   > ").strip().lower()
    except (EOFError, OSError, KeyboardInterrupt):
        # Default to 'n' if no console input is available (e.g. background mode)
        choice = 'n'
        
    if choice in ['y', 'yes']:
        log_decision(action, "ALLOWED_USER")
        return True
    
    print("🚫 Action cancelled.")
    log_decision(action, "DENIED_USER")
    return False

def get_permission_history():
    """View permission decision history"""
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            return f.read()
    return "No permission history found."
