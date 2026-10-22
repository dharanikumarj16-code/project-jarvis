import pytest
from app.router import ExecutionContext, split_commands, plan_user_input, match_direct_command

def test_split_commands_various_separators():
    # && separator
    assert split_commands('open notepad && close notepad') == ['open notepad', 'close notepad']
    # ; separator
    assert split_commands('open notepad; close notepad') == ['open notepad', 'close notepad']
    # newline separator
    assert split_commands('open notepad\nclose notepad') == ['open notepad', 'close notepad']
    # comma separator
    assert split_commands('open notepad, close notepad') == ['open notepad', 'close notepad']
    # ' and ' separator
    assert split_commands('open notepad and close notepad') == ['open notepad', 'close notepad']
    # mixed separators
    assert split_commands('open notepad && type hello and maximize it') == ['open notepad', 'type hello', 'maximize it']

def test_plan_user_input_and_execution_context_update():
    ctx = ExecutionContext()
    steps = plan_user_input('open notepad && type hello world and maximize it', ctx)
    # Expect three steps
    assert len(steps) == 3
    # First step
    assert steps[0].command == 'open notepad'
    assert steps[0].tool_name == 'open_app'
    assert steps[0].tool_args == {'app_name': 'notepad'}
    # Second step (type)
    assert steps[1].tool_name == 'type_text'
    assert steps[1].tool_args == {'text': 'hello world'}
    # Third step (maximize) – pronoun not resolved yet in initial parse
    assert steps[2].tool_name == 'maximize_window'
    assert steps[2].tool_args == {}

    # Simulate opening app to set context via update method
    ctx.update('open_app', {'app_name': 'notepad'})
    assert ctx.last_app_name == 'notepad'

    # Now re-resolve using match_direct_command as done during execution
    step3 = match_direct_command(steps[2].command, ctx)
    assert step3.tool_name == 'maximize_window'
    assert step3.tool_args == {'app_name': 'notepad'}

def test_match_direct_command_pronoun_resolution():
    ctx = ExecutionContext(last_app_name='notepad')
    step = match_direct_command('maximize it', ctx)
    assert step.tool_name == 'maximize_window'
    # Pronoun "it" should be resolved to last_app_name
    assert step.tool_args == {'app_name': 'notepad'}


def test_press_window_button_and_shortcuts():
    ctx = ExecutionContext()
    # 1. press window button
    step1 = match_direct_command("press window button", ctx)
    assert step1.tool_name == "press_key"
    assert step1.tool_args == {"key": "window button"}

    # 2. press ctrl c
    step2 = match_direct_command("press ctrl c", ctx)
    assert step2.tool_name == "press_key"
    assert step2.tool_args == {"key": "ctrl c"}

    # 3. shortcut copy
    step3 = match_direct_command("shortcut copy", ctx)
    assert step3.tool_name == "macro_shortcut"
    assert step3.tool_args == {"action": "copy"}

    # 4. press shortcut task manager
    step4 = match_direct_command("press shortcut task manager", ctx)
    assert step4.tool_name == "press_key"
    assert step4.tool_args == {"key": "task manager"}


def test_mouse_optimization_routing():
    ctx = ExecutionContext()
    # 1. right click
    s1 = match_direct_command("right click", ctx)
    assert s1.tool_name == "mouse_right_click"

    # 2. double click
    s2 = match_direct_command("double click", ctx)
    assert s2.tool_name == "mouse_double_click"

    # 3. click with coordinates
    s3 = match_direct_command("click 500 300", ctx)
    assert s3.tool_name == "mouse_click"
    assert s3.tool_args.get("x") == 500
    assert s3.tool_args.get("y") == 300

    # 4. move mouse to coordinates
    s4 = match_direct_command("move mouse to 600 400", ctx)
    assert s4.tool_name == "mouse_move"
    assert s4.tool_args.get("x") == 600
    assert s4.tool_args.get("y") == 400

    # 5. scroll down and scroll up
    s5 = match_direct_command("scroll down", ctx)
    assert s5.tool_name == "mouse_scroll"
    assert s5.tool_args.get("clicks") == -5

    s6 = match_direct_command("scroll up", ctx)
    assert s6.tool_name == "mouse_scroll"
    assert s6.tool_args.get("clicks") == 5

    # 6. mouse position
    s7 = match_direct_command("mouse position", ctx)
    assert s7.tool_name == "mouse_get_position"

    # 7. drag mouse
    s8 = match_direct_command("drag mouse 800 600", ctx)
    assert s8.tool_name == "mouse_drag"
    assert s8.tool_args.get("x") == 800
    assert s8.tool_args.get("y") == 600


def test_semantic_intent_routing_with_fastembed():
    """Verify that conversational commands not caught by verb map resolve via semantic embedding."""
    from app.router import get_fastembed_model
    model = get_fastembed_model()
    assert model is not None, "fastembed model should be available"

    ctx = ExecutionContext()
    # Conversational phrasing that does not start with standard VERB_TOOL_MAP verbs:
    step = match_direct_command("please launch application chrome", ctx)
    assert step.is_direct is True
    assert step.tool_name == "open_app"
    assert step.tool_args.get("app_name") == "chrome"

    step_screenshot = match_direct_command("capture current display", ctx)
    assert step_screenshot.is_direct is True
    assert step_screenshot.tool_name == "take_screenshot"


def test_list_files_and_folders_routing_and_output():
    """Verify that file/folder listing commands route cleanly and format output."""
    from app.core import _format_clean_tool_output

    ctx = ExecutionContext()

    # 1. "list files"
    s1 = match_direct_command("list files", ctx)
    assert s1.tool_name == "list_directory"
    assert s1.tool_args.get("path") == "."

    # 2. "list file folders" (user's specific request)
    s2 = match_direct_command("list file folders", ctx)
    assert s2.tool_name == "list_directory"
    assert s2.tool_args.get("path") == "."

    # 3. "list files and folders"
    s3 = match_direct_command("list files and folders", ctx)
    assert s3.tool_name == "list_directory"
    assert s3.tool_args.get("path") == "."

    # 4. "list folders in test_sandbox"
    s4 = match_direct_command("list folders in test_sandbox", ctx)
    assert s4.tool_name == "list_directory"
    assert s4.tool_args.get("path") == "test_sandbox"

    # 5. Format clean tool output test
    mock_raw_result = {
        "success": True,
        "tool_name": "list_directory",
        "data": {
            "success": True,
            "path": "C:\\test_dir",
            "total_count": 2,
            "returned_count": 2,
            "entries": [
                {"name": "subfolder", "is_dir": True, "size_formatted": None},
                {"name": "test.txt", "is_dir": False, "size_formatted": "12 KB"},
            ],
        },
        "error": None,
    }
    output = _format_clean_tool_output("list_directory", {"path": "."}, mock_raw_result)
    assert "Directory: C:\\test_dir (2 items)" in output
    assert "📁 [DIR]  subfolder" in output
    assert "📄 [FILE] test.txt" in output
    assert "12 KB" in output


