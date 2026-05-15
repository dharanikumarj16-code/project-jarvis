import json
import logging
from core.commands.base import BaseCommand
from integrations.ollama_wrapper import execute_agent_goal
from integrations.automation import execute_sequence

class ComplexGoalCommand(BaseCommand):
    """
    Command that uses LLM to decompose a complex goal into automation steps.
    """

    def execute(self, args: dict) -> str:
        goal = args.get("goal")
        if not goal:
            return "No goal provided for complex reasoning."

        prompt = f"""
        You are an autonomous agent controlling a computer.
        Your goal is: {goal}
        
        Decompose this goal into a sequence of atomic actions.
        Available actions:
        - {{"action": "open", "params": ["app_name"]}}
        - {{"action": "type", "params": ["text"]}}
        - {{"action": "press", "params": ["key"]}} (e.g., "enter", "ctrl+s")
        - {{"action": "click", "params": [x, y]}} or {{"action": "click", "params": ["right"]}}
        - {{"action": "wait", "params": [seconds]}}
        - {{"action": "scroll", "params": [amount]}} (positive for up, negative for down)

        Return ONLY a JSON list of steps. No explanation.
        Example:
        [
            {{"action": "open", "params": ["notepad"]}},
            {{"action": "type", "params": ["Hello World"]}},
            {{"action": "press", "params": ["ctrl+s"]}}
        ]
        """

        print(f"🧠 Reasoning about goal: {goal}")
        response = execute_agent_goal(prompt)
        
        try:
            # Try to find JSON in the response
            start_idx = response.find('[')
            end_idx = response.rfind(']') + 1
            if start_idx != -1 and end_idx != 0:
                json_str = response[start_idx:end_idx]
                steps = json.loads(json_str)
            else:
                # Try parsing the whole response
                steps = json.loads(response)
            
            if not isinstance(steps, list):
                return f"LLM returned invalid format (not a list): {response}"

            success = execute_sequence(steps)
            if success:
                return f"Successfully completed complex goal: {goal}"
            else:
                return f"Failed to execute some steps for goal: {goal}"

        except (json.JSONDecodeError, ValueError) as e:
            logging.error(f"Failed to parse LLM response: {response}")
            return f"Error parsing LLM plan: {str(e)}. Response was: {response}"

    def extract_args(self, text: str) -> dict:
        # For complex goal, the entire text might be the goal
        # but we can strip some keywords if needed.
        goal = text
        prefixes = ["complex ", "autonomous ", "do everything ", "can you ", "do "]
        for prefix in prefixes:
            if goal.lower().startswith(prefix):
                goal = goal[len(prefix):]
                break
        return {"goal": goal.strip()}
