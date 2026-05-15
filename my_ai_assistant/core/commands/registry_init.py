from core.commands.registry import registry
from core.commands.system_commands import (
    TellTimeCommand, TellDateCommand, OpenNotepadCommand, 
    OpenBrowserCommand, OpenCalculatorCommand
)
from core.commands.device_commands import (
    TypeTextCommand, ScrollCommand, ClickCommand, 
    PressEnterCommand, HotkeyCommand
)
from core.commands.task_commands import AddTaskCommand
from core.commands.web_commands import SearchWebCommand
from core.commands.whatsapp_commands import (
    WhatsAppOpenChatCommand, WhatsAppTypeAndSendCommand,
    WhatsAppClearTextCommand, WhatsAppAddNewLineCommand,
    WhatsAppAttachFileCommand, WhatsAppSendMessageCommand
)
from core.commands.vision_commands import VisionAnalyzeCommand
from core.commands.ai_commands import ComplexGoalCommand

def initialize_commands():
    # System Commands
    registry.register("tell_time", TellTimeCommand())
    registry.register("tell_date", TellDateCommand())
    registry.register("open_notepad", OpenNotepadCommand())
    registry.register("open_browser", OpenBrowserCommand())
    registry.register("open_calculator", OpenCalculatorCommand())

    # AI Commands
    registry.register("complex_goal", ComplexGoalCommand())

    # Device Commands
    registry.register("type_text", TypeTextCommand())
    registry.register("scroll_up", ScrollCommand("up"))
    registry.register("scroll_down", ScrollCommand("down"))
    registry.register("click_mouse", ClickCommand("left"))
    registry.register("right_click", ClickCommand("right"))
    registry.register("press_enter", PressEnterCommand())
    
    # Hotkey Commands
    registry.register("system_copy", HotkeyCommand("ctrl", "c"))
    registry.register("system_paste", HotkeyCommand("ctrl", "v"))
    registry.register("system_cut", HotkeyCommand("ctrl", "x"))
    registry.register("system_select_all", HotkeyCommand("ctrl", "a"))
    registry.register("system_close_tab", HotkeyCommand("ctrl", "w"))
    registry.register("system_minimize", HotkeyCommand("win", "down"))
    registry.register("system_new_tab", HotkeyCommand("ctrl", "t"))
    registry.register("system_show_desktop", HotkeyCommand("win", "d"))
    registry.register("system_go_home", HotkeyCommand("alt", "home"))
    registry.register("take_screenshot", HotkeyCommand("win", "shift", "s"))
    registry.register("screen_record", HotkeyCommand("win", "alt", "r"))

    # Task Commands
    registry.register("add_task", AddTaskCommand())

    # Web Commands
    registry.register("search_web", SearchWebCommand())

    # WhatsApp Commands
    registry.register("whatsapp_open_chat", WhatsAppOpenChatCommand())
    registry.register("whatsapp_type_and_send", WhatsAppTypeAndSendCommand())
    registry.register("whatsapp_clear_text", WhatsAppClearTextCommand())
    registry.register("whatsapp_add_new_line", WhatsAppAddNewLineCommand())
    registry.register("whatsapp_attach_file", WhatsAppAttachFileCommand())
    registry.register("whatsapp_send_message", WhatsAppSendMessageCommand())

    # Vision Commands
    registry.register("vision_analyze", VisionAnalyzeCommand())

if __name__ == "__main__":
    initialize_commands()
    print("Commands initialized.")
