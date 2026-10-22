"""
tests/test_nlp_router_intelligent.py  –  Comprehensive Evaluation & Benchmarking Suite
======================================================================================

Validates the Intelligent 6-Layer NLP Router for JARVIS OS:
1. All prompt examples (misspelled, informal, short voice commands).
2. Literal preservation without rewriting filenames (e.g. 'teh.py').
3. Canonical tool registry metadata & alias recovery.
4. Context-aware pronoun and selection resolution.
5. Clarification generation for ambiguous requests.
6. End-to-end latency and performance benchmarks (< 10ms for fast paths).
"""

import time
import pytest
from app.router import (
    ExecutionContext,
    match_direct_command,
    plan_user_input,
    _nlp_router,
    RoutingResult,
)
from app.nlp_corrector import nlp_corrector
from app.tools.canonical_registry import (
    get_canonical_registry,
    get_canonical_tool_record,
    resolve_canonical_tool_name,
)


# ---------------------------------------------------------------------------
# 1. Verification of the 12 User Prompt Examples
# ---------------------------------------------------------------------------

def test_example_open_file_explorer_misspelled():
    """'opn file exploer' → open File Explorer."""
    ctx = ExecutionContext()
    step = match_direct_command("opn file exploer", ctx)
    assert step.is_direct is True
    assert step.tool_name == "file_explorer_open"
    assert step.routing_result.routing_layer in ("normalized", "exact", "semantic")


def test_example_create_folder_projects_misspelled():
    """'creat foler projcts' → create a folder named projects."""
    ctx = ExecutionContext()
    step = match_direct_command("creat foler projcts", ctx)
    assert step.is_direct is True
    assert step.tool_name == "create_directory"
    assert "project" in step.tool_args.get("path", "").lower()


def test_example_change_file_name_clarification_and_execution():
    """'chage file nme' → rename a file (requests clarification if no args, renames if paths given)."""
    ctx = ExecutionContext()
    # Case A: Missing arguments triggers Layer 6 clarification
    step_clarify = match_direct_command("chage file nme", ctx)
    assert step_clarify.routing_result.needs_clarification is True
    assert "rename" in step_clarify.routing_result.clarification_prompt.lower()

    # Case B: Arguments provided
    step_exec = match_direct_command("chage file nme old.txt to new.txt", ctx)
    assert step_exec.is_direct is True
    assert step_exec.tool_name == "rename_path"
    assert step_exec.tool_args.get("source") == "old.txt"
    assert step_exec.tool_args.get("new_name_or_path") == "new.txt"


def test_example_move_pdfs_to_documents_misspelled():
    """'mov pdfs to documnts' → move PDF files to Documents."""
    ctx = ExecutionContext()
    step = match_direct_command("mov pdfs to documnts", ctx)
    assert step.is_direct is True
    assert step.tool_name in ("batch_move", "move_file")
    assert "pdf" in str(step.tool_args.get("source") or step.tool_args.get("pattern"))
    assert "document" in str(step.tool_args.get("destination") or step.tool_args.get("destination_dir")).lower()


def test_example_delete_this_folder_misspelled():
    """'delte this foler' → delete the specified folder safely."""
    ctx = ExecutionContext(last_path="C:\\test_folder")
    step = match_direct_command("delte this foler", ctx)
    assert step.is_direct is True
    assert step.tool_name == "move_to_recycle_bin"


def test_example_list_all_py_files():
    """'list all py files' → search for Python files."""
    ctx = ExecutionContext()
    step = match_direct_command("list all py files", ctx)
    assert step.is_direct is True
    assert step.tool_name == "search_files"
    assert step.tool_args.get("query") == "*.py"


def test_example_open_chrome_misspelled():
    """'open chrme' → open Chrome."""
    ctx = ExecutionContext()
    step = match_direct_command("open chrme", ctx)
    assert step.is_direct is True
    assert step.tool_name == "open_app"
    assert step.tool_args.get("app_name") == "chrome"


def test_example_right_click_misspelled():
    """'right clik' → right-click."""
    ctx = ExecutionContext()
    step = match_direct_command("right clik", ctx)
    assert step.is_direct is True
    assert step.tool_name == "mouse_right_click"


def test_example_scroll_down_misspelled():
    """'scroll dwn' → scroll down."""
    ctx = ExecutionContext()
    step = match_direct_command("scroll dwn", ctx)
    assert step.is_direct is True
    assert step.tool_name == "mouse_scroll"
    assert step.tool_args.get("clicks", 0) < 0


def test_example_run_terminal_command():
    """'run termnal cmd' → use registered terminal tool."""
    ctx = ExecutionContext()
    # With command
    step = match_direct_command("run termnal cmd dir", ctx)
    assert step.is_direct is True
    assert step.tool_name == "terminal_execute"
    assert "dir" in step.tool_args.get("command", "")


def test_example_find_duplicate_files_misspelled():
    """'find duplicate fil' → find duplicate files."""
    ctx = ExecutionContext()
    step = match_direct_command("find duplicate fil", ctx)
    assert step.is_direct is True
    assert step.tool_name == "find_duplicate_files"


def test_example_undo_last_operation_misspelled():
    """'undo last opration' → invoke recovery operation."""
    ctx = ExecutionContext()
    step = match_direct_command("undo last opration", ctx)
    assert step.is_direct is True
    assert step.tool_name == "undo_supported_file_operation"


# ---------------------------------------------------------------------------
# 2. Literal Preservation Test (teh.py MUST NOT become the.py)
# ---------------------------------------------------------------------------

def test_literal_preservation_teh_py():
    """Verify that literal filenames like 'teh.py' are strictly preserved."""
    ctx = ExecutionContext()
    step = match_direct_command("create file named teh.py", ctx)
    assert step.is_direct is True
    assert step.tool_name == "create_file"
    assert step.tool_args.get("path") == "teh.py", "Filename 'teh.py' must NOT be rewritten to 'the.py'!"

    norm_text, _, _ = nlp_corrector.normalize("creat a file named teh.py")
    assert "teh.py" in norm_text
    assert "the.py" not in norm_text


# ---------------------------------------------------------------------------
# 3. Canonical Registry & Hallucinated Name Recovery
# ---------------------------------------------------------------------------

def test_canonical_registry_and_alias_recovery():
    """Verify registry reflection and recovery of model-hallucinated function names."""
    registry = get_canonical_registry()
    assert len(registry) >= 15
    assert "file_explorer_open" in registry
    assert "rename_path" in registry
    assert "terminal_execute" in registry

    # Hallucinated alias resolution
    assert resolve_canonical_tool_name("file_manager_open") == "file_explorer_open"
    assert resolve_canonical_tool_name("delete_file") == "move_to_recycle_bin"
    assert resolve_canonical_tool_name("find_files") == "search_files"
    assert resolve_canonical_tool_name("change_filename") == "rename_path"
    assert resolve_canonical_tool_name("run_command") == "terminal_execute"


# ---------------------------------------------------------------------------
# 4. Context-Aware Routing & Reference Resolution
# ---------------------------------------------------------------------------

def test_context_aware_pronoun_resolution():
    """Verify context-aware reference resolution with 'it'."""
    ctx = ExecutionContext(last_selection="report_draft.pdf")
    step = match_direct_command("rename it to final_report.pdf", ctx)
    assert step.is_direct is True
    assert step.tool_name == "rename_path"
    assert step.tool_args.get("source") == "report_draft.pdf"
    assert step.tool_args.get("new_name_or_path") == "final_report.pdf"


# ---------------------------------------------------------------------------
# 5. Multi-Step Workflows
# ---------------------------------------------------------------------------

def test_multi_step_workflow_parsing():
    """Verify sequential command splitting and multi-step dispatch."""
    ctx = ExecutionContext()
    steps = plan_user_input("opn file exploer && creat foler projcts && list files", ctx)
    assert len(steps) == 3
    assert steps[0].tool_name == "file_explorer_open"
    assert steps[1].tool_name == "create_directory"
    assert steps[2].tool_name == "list_directory"
    assert all(s.is_direct for s in steps)


# ---------------------------------------------------------------------------
# 6. Performance & Latency Benchmarks
# ---------------------------------------------------------------------------

def test_routing_latency_benchmark():
    """Verify low-latency deterministic and normalized matching (< 10ms median)."""
    ctx = ExecutionContext()
    benchmark_queries = [
        "list files",
        "opn file exploer",
        "scroll dwn",
        "right clik",
        "creat foler projcts",
        "find duplicate fil",
        "undo last opration",
        "open chrme",
    ]

    latencies_ms = []
    for _ in range(10):
        for q in benchmark_queries:
            t0 = time.perf_counter()
            step = match_direct_command(q, ctx)
            dt = (time.perf_counter() - t0) * 1000.0
            latencies_ms.append(dt)
            assert step.is_direct is True

    latencies_ms.sort()
    median_latency = latencies_ms[len(latencies_ms) // 2]
    p95_latency = latencies_ms[int(len(latencies_ms) * 0.95)]

    print(f"\n[NLP Router Benchmark] Median latency: {median_latency:.3f}ms | P95 latency: {p95_latency:.3f}ms")
    assert median_latency < 10.0, f"Expected median latency < 10ms, got {median_latency:.2f}ms"


# ---------------------------------------------------------------------------
# 7. Windows Button Search Easy Method
# ---------------------------------------------------------------------------

def test_windows_button_search_routing():
    """Verify that general search requests map to Windows button search (windows_search)."""
    ctx = ExecutionContext()

    # 1. Direct search queries map to Windows button search
    step1 = match_direct_command("search notepad", ctx)
    assert step1.is_direct is True
    assert step1.tool_name == "windows_search"
    assert step1.tool_args.get("query") == "notepad"

    # 2. Windows search explicit phrasing
    step2 = match_direct_command("windows search spotify", ctx)
    assert step2.is_direct is True
    assert step2.tool_name == "windows_search"
    assert step2.tool_args.get("query") == "spotify"

    # 3. Windows button search phrasing
    step3 = match_direct_command("windows button search calc", ctx)
    assert step3.is_direct is True
    assert step3.tool_name == "windows_search"
    assert step3.tool_args.get("query") == "calc"

    # 4. Search for phrasing
    step4 = match_direct_command("search for control panel", ctx)
    assert step4.is_direct is True
    assert step4.tool_name == "windows_search"
    assert step4.tool_args.get("query") == "control panel"

    # 5. Explicit web search remains web_search
    step5 = match_direct_command("web search python tutorials", ctx)
    assert step5.is_direct is True
    assert step5.tool_name == "web_search"
    assert step5.tool_args.get("query") == "python tutorials"

    # 6. Explicit file search remains search_files
    step6 = match_direct_command("search all py files", ctx)
    assert step6.is_direct is True
    assert step6.tool_name == "search_files"
    assert step6.tool_args.get("query") == "*.py"


# ---------------------------------------------------------------------------
# 8. Browser Search & Google Search Routing
# ---------------------------------------------------------------------------

def test_browser_search_and_google_search_routing():
    """Verify that browser search and google search route cleanly to browser_search,
    while windows search for google remains windows_search."""
    ctx = ExecutionContext()

    # 1. browser search
    s1 = match_direct_command("browser search latest ai news", ctx)
    assert s1.is_direct is True
    assert s1.tool_name == "browser_search"
    assert "latest ai news" in s1.tool_args.get("query", "")

    # 2. google search
    s2 = match_direct_command("google search machine learning", ctx)
    assert s2.is_direct is True
    assert s2.tool_name == "browser_search"
    assert "machine learning" in s2.tool_args.get("query", "")

    # 3. search google for ...
    s3 = match_direct_command("search google for recipes", ctx)
    assert s3.is_direct is True
    assert s3.tool_name == "browser_search"
    assert "recipes" in s3.tool_args.get("query", "")

    # 4. direct 'google ...' command
    s4 = match_direct_command("google weather in paris", ctx)
    assert s4.is_direct is True
    assert s4.tool_name == "browser_search"
    assert "weather in paris" in s4.tool_args.get("query", "")

    # 5. typo: 'browser serach ...'
    s5 = match_direct_command("browser serach quantum computing", ctx)
    assert s5.is_direct is True
    assert s5.tool_name == "browser_search"
    assert "quantum computing" in s5.tool_args.get("query", "")

    # 6. typo: 'gooogle serach ...'
    s6 = match_direct_command("gooogle serach stock market", ctx)
    assert s6.is_direct is True
    assert s6.tool_name == "browser_search"
    assert "stock market" in s6.tool_args.get("query", "")

    # 7. 'search on windows google' -> routes to windows button search
    s7 = match_direct_command("search on windows google", ctx)
    assert s7.is_direct is True
    assert s7.tool_name == "windows_search"
    assert "google" in s7.tool_args.get("query", "")

    # 8. 'search windows for google chrome' -> routes to windows button search
    s8 = match_direct_command("search windows for google chrome", ctx)
    assert s8.is_direct is True
    assert s8.tool_name == "windows_search"
    assert "google chrome" in s8.tool_args.get("query", "")


# ---------------------------------------------------------------------------
# 9. Browser Shortcuts, State, Search Bar & WhatsApp Tests
# ---------------------------------------------------------------------------

def test_browser_shortcuts_map():
    """Verify that browser shortcut mappings exist in SHORTCUT_MAP."""
    from app.tools.macros import SHORTCUT_MAP, execute_mapped_shortcut
    # Tab shortcuts
    assert SHORTCUT_MAP["new tab"] == ["ctrl", "t"]
    assert SHORTCUT_MAP["close tab"] == ["ctrl", "w"]
    assert SHORTCUT_MAP["reopen tab"] == ["ctrl", "shift", "t"]
    assert SHORTCUT_MAP["next tab"] == ["ctrl", "tab"]
    assert SHORTCUT_MAP["previous tab"] == ["ctrl", "shift", "tab"]
    assert SHORTCUT_MAP["tab 1"] == ["ctrl", "1"]
    assert SHORTCUT_MAP["tab 8"] == ["ctrl", "8"]

    # Navigation
    assert SHORTCUT_MAP["back"] == ["alt", "left"]
    assert SHORTCUT_MAP["forward"] == ["alt", "right"]
    assert SHORTCUT_MAP["refresh"] == ["ctrl", "r"]
    assert SHORTCUT_MAP["hard refresh"] == ["ctrl", "f5"]
    assert SHORTCUT_MAP["stop loading"] == ["esc"]
    assert SHORTCUT_MAP["fullscreen"] == ["f11"]

    # Search & Zoom
    assert SHORTCUT_MAP["search bar"] == ["ctrl", "k"]
    assert SHORTCUT_MAP["focus search bar"] == ["ctrl", "k"]
    assert SHORTCUT_MAP["address bar"] == ["ctrl", "l"]
    assert SHORTCUT_MAP["find"] == ["ctrl", "f"]
    assert SHORTCUT_MAP["zoom in"] == ["ctrl", "+"]
    assert SHORTCUT_MAP["zoom out"] == ["ctrl", "-"]
    assert SHORTCUT_MAP["reset zoom"] == ["ctrl", "0"]

    # History & Media
    assert SHORTCUT_MAP["history"] == ["ctrl", "h"]
    assert SHORTCUT_MAP["downloads"] == ["ctrl", "j"]
    assert SHORTCUT_MAP["bookmark"] == ["ctrl", "d"]
    assert SHORTCUT_MAP["incognito"] == ["ctrl", "shift", "n"]
    assert SHORTCUT_MAP["play"] == ["space"]
    assert SHORTCUT_MAP["pause"] == ["space"]


def test_state_and_whatsapp_and_uia_routing():
    """Verify that current state, search bar, WhatsApp, and UIA button commands route directly."""
    ctx = ExecutionContext()

    # 1. State detection
    st1 = match_direct_command("current state", ctx)
    assert st1.is_direct is True
    assert st1.tool_name == "get_current_desktop_state"

    st2 = match_direct_command("desktop state", ctx)
    assert st2.is_direct is True
    assert st2.tool_name == "get_current_desktop_state"

    st3 = match_direct_command("which desktop", ctx)
    assert st3.is_direct is True
    assert st3.tool_name == "get_current_desktop_state"

    # 2. Browser Search Bar (Ctrl+K)
    sb1 = match_direct_command("search bar python tutorials", ctx)
    assert sb1.is_direct is True
    assert sb1.tool_name == "browser_search_bar"
    assert "python tutorials" in sb1.tool_args.get("query", "")

    sb2 = match_direct_command("ctrl k machine learning", ctx)
    assert sb2.is_direct is True
    assert sb2.tool_name == "browser_search_bar"

    # 3. WhatsApp Messaging & Searching
    w1 = match_direct_command("whatsapp message John hello how are you", ctx)
    assert w1.is_direct is True
    assert w1.tool_name == "whatsapp_search_and_message"
    assert "John" in w1.tool_args.get("contact", "")
    assert "hello how are you" in w1.tool_args.get("message", "")

    w2 = match_direct_command("whatsapp search Alice", ctx)
    assert w2.is_direct is True
    assert w2.tool_name == "whatsapp_search_and_message"
    assert "Alice" in w2.tool_args.get("contact", "")

    # 4. UIA Button Actions (Like, Send, Submit, Enter)
    u1 = match_direct_command("click like", ctx)
    assert u1.is_direct is True
    assert u1.tool_name == "uia_click_button"
    assert u1.tool_args.get("role") == "like"

    u2 = match_direct_command("send button", ctx)
    assert u2.is_direct is True
    assert u2.tool_name == "uia_click_button"
    assert u2.tool_args.get("role") == "send"

    u3 = match_direct_command("enter button", ctx)
    assert u3.is_direct is True
    assert u3.tool_name == "uia_click_button"
    assert u3.tool_args.get("role") == "enter"

    u4 = match_direct_command("submit button", ctx)
    assert u4.is_direct is True
    assert u4.tool_name == "uia_click_button"
    assert u4.tool_args.get("role") == "submit"


# ---------------------------------------------------------------------------
# 10. Play Song & Music Routing Tests
# ---------------------------------------------------------------------------

def test_play_song_and_media_routing():
    """Verify that 'play song <title>', 'play music', 'play <title>' route to play_music."""
    ctx = ExecutionContext()

    # 1. Play song with title
    p1 = match_direct_command("play song believer", ctx)
    assert p1.is_direct is True
    assert p1.tool_name == "play_music"
    assert "believer" in p1.tool_args.get("query", "")

    # 2. Direct play <title>
    p2 = match_direct_command("play shape of you", ctx)
    assert p2.is_direct is True
    assert p2.tool_name == "play_music"
    assert "shape of you" in p2.tool_args.get("query", "")

    # 3. Play music <genre/title>
    p3 = match_direct_command("play music lofi beats", ctx)
    assert p3.is_direct is True
    assert p3.tool_name == "play_music"
    assert "lofi beats" in p3.tool_args.get("query", "")

    # 4. Toggle play/pause (empty title)
    p4 = match_direct_command("play song", ctx)
    assert p4.is_direct is True
    assert p4.tool_name == "play_music"

    # 5. Play on youtube
    p5 = match_direct_command("play song on youtube heat waves", ctx)
    assert p5.is_direct is True
    assert p5.tool_name == "play_music"
    assert "heat waves" in p5.tool_args.get("query", "")


def test_click_first_link_routing():
    """Verify that 'click below link', 'click first link', 'click first video' route to click_first_link."""
    ctx = ExecutionContext()

    c1 = match_direct_command("click below link", ctx)
    assert c1.is_direct is True
    assert c1.tool_name == "click_first_link"

    c2 = match_direct_command("click first link", ctx)
    assert c2.is_direct is True
    assert c2.tool_name == "click_first_link"

    c3 = match_direct_command("click below first link", ctx)
    assert c3.is_direct is True
    assert c3.tool_name == "click_first_link"

    c4 = match_direct_command("click first video", ctx)
    assert c4.is_direct is True
    assert c4.tool_name == "click_first_link"

    c5 = match_direct_command("click top link", ctx)
    assert c5.is_direct is True
    assert c5.tool_name == "click_first_link"


# ---------------------------------------------------------------------------
# 11. Multi-Platform Play Mode & Directional Mouse Tests
# ---------------------------------------------------------------------------

def test_play_music_optional_platforms():
    """Verify that play commands support optional platforms (Hotstar, Spotify, Netflix) with default YouTube."""
    ctx = ExecutionContext()

    # 1. Default platform is YouTube
    p1 = match_direct_command("play believer", ctx)
    assert p1.is_direct is True
    assert p1.tool_name == "play_music"
    assert p1.tool_args.get("platform") == "youtube"
    assert "believer" in p1.tool_args.get("query", "")

    # 2. Hotstar / JioHotstar
    p2 = match_direct_command("play cricket on hotstar", ctx)
    assert p2.is_direct is True
    assert p2.tool_name == "play_music"
    assert p2.tool_args.get("platform") == "hotstar"
    assert "cricket" in p2.tool_args.get("query", "")

    # 3. JioCinema / JioHotstar
    p3 = match_direct_command("play movie on jio cinema", ctx)
    assert p3.is_direct is True
    assert p3.tool_name == "play_music"
    assert p3.tool_args.get("platform") == "hotstar"

    # 4. Spotify
    p4 = match_direct_command("play heat waves on spotify", ctx)
    assert p4.is_direct is True
    assert p4.tool_name == "play_music"
    assert p4.tool_args.get("platform") == "spotify"
    assert "heat waves" in p4.tool_args.get("query", "")

    # 5. Netflix
    p5 = match_direct_command("play stranger things on netflix", ctx)
    assert p5.is_direct is True
    assert p5.tool_name == "play_music"
    assert p5.tool_args.get("platform") == "netflix"
    # 6. Jio hostar (typo tolerance)
    p6 = match_direct_command("play live match on jio hostar", ctx)
    assert p6.is_direct is True
    assert p6.tool_name == "play_music"
    assert p6.tool_args.get("platform") == "hotstar"
    assert "live match" in p6.tool_args.get("query", "")


def test_directional_mouse_movements():
    """Verify that 'mouse move up', 'down', 'left', 'right' route to mouse_move with direction & distance."""
    ctx = ExecutionContext()

    # Up
    m1 = match_direct_command("mouse move up", ctx)
    assert m1.is_direct is True
    assert m1.tool_name == "mouse_move"
    assert m1.tool_args.get("direction") == "up"

    # Down with distance
    m2 = match_direct_command("mouse move down 150", ctx)
    assert m2.is_direct is True
    assert m2.tool_name == "mouse_move"
    assert m2.tool_args.get("direction") == "down"
    assert m2.tool_args.get("distance") == 150

    # Left
    m3 = match_direct_command("move mouse left", ctx)
    assert m3.is_direct is True
    assert m3.tool_name == "mouse_move"
    assert m3.tool_args.get("direction") == "left"

    # Right with distance
    m4 = match_direct_command("move mouse right 200", ctx)
    assert m4.is_direct is True
    assert m4.tool_name == "mouse_move"
    assert m4.tool_args.get("direction") == "right"
    assert m4.tool_args.get("distance") == 200

    # Short commands: mouse up, mouse right, mouse left
    m5 = match_direct_command("mouse right", ctx)
    assert m5.is_direct is True
    assert m5.tool_name == "mouse_move"
    assert m5.tool_args.get("direction") == "right"


def test_click_content_area_routing():
    """Verify that clicking content areas (box, text, icon, quoted text) routes to click_ui_content."""
    ctx = ExecutionContext()

    # 1. Quoted content area: click " content" content area
    c1 = match_direct_command('click " content" content area', ctx)
    assert c1.is_direct is True
    assert c1.tool_name == "click_ui_content"
    assert c1.tool_args.get("query") == "content"

    # 2. Quoted content: click "Search"
    c2 = match_direct_command('click "Search"', ctx)
    assert c2.is_direct is True
    assert c2.tool_name == "click_ui_content"
    assert c2.tool_args.get("query") == "Search"

    # 3. Box content: click box "username"
    c3 = match_direct_command('click box "username"', ctx)
    assert c3.is_direct is True
    assert c3.tool_name == "click_ui_content"
    assert c3.tool_args.get("query") == "username"
    assert c3.tool_args.get("element_type") == "box"

    # 4. Text content: click text "Login"
    c4 = match_direct_command('click text "Login"', ctx)
    assert c4.is_direct is True
    assert c4.tool_name == "click_ui_content"
    assert c4.tool_args.get("query") == "Login"
    assert c4.tool_args.get("element_type") == "text"

    # 5. Icon content: click icon "settings"
    c5 = match_direct_command('click icon "settings"', ctx)
    assert c5.is_direct is True
    assert c5.tool_name == "click_ui_content"
    assert c5.tool_args.get("query") == "settings"
    assert c5.tool_args.get("element_type") == "icon"

    # 6. Click content phrase: click content "profile"
    c6 = match_direct_command('click content "profile"', ctx)
    assert c6.is_direct is True
    assert c6.tool_name == "click_ui_content"
    assert c6.tool_args.get("query") == "profile"





