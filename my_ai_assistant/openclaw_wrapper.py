import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def safety_filter(command):
    """
    Analyzes the command for potential safety risks before execution.
    Returns True if safe, False otherwise.
    """
    # Basic keyword filtering for safety
    unsafe_keywords = [
        "rm -rf", "format", "delete system32", "wipe", 
        "shutdown", "reboot", "mkfs", ":(){ :|:& };:"
    ]
    
    command_lower = command.lower()
    for keyword in unsafe_keywords:
        if keyword in command_lower:
            return False
            
    return True

def execute_agent_goal(goal):
    """
    Routes complex goals to the OpenClaw agent.
    """
    # TODO: Integrate with the actual OpenClaw library once installed
    # Example:
    # from openclaw.core import Agent
    # agent = Agent()
    # return agent.run(goal)
    
    return f"OpenClaw Agent received goal: '{goal}'. (Integration pending installation)"