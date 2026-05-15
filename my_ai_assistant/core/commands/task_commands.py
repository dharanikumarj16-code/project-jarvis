import re
from core.commands.base import BaseCommand
from core.memory import add_task, log_usage

class AddTaskCommand(BaseCommand):
    """
    Command to add a new task to the task list.
    """
    def execute(self, args: dict) -> str:
        task_desc = args.get("description")
        if not task_desc:
            return "Please specify what task to add."
        
        result = add_task(task_desc)
        log_usage("add_task", True)
        return result

    def extract_args(self, text: str) -> dict:
        # Pattern matching for 'add task [description]' or 'add a task [description]'
        task_desc = re.sub(r'^add (a )?task\s*', '', text, flags=re.IGNORECASE).strip()
        
        if task_desc:
            return {"description": task_desc}
        return {}
