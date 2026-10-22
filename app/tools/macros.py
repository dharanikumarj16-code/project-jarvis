import time
from app.tools.computer.keyboard import KeyboardController
from app.tools.computer.mouse import MouseController
from app.tools.window_manager import window_focus

def windows_menu_search(query: str, press_enter: bool = True):
    """Opens Windows Search via the Windows button (Win key), types the query, and presses Enter to launch."""
    kbd = KeyboardController()
    clean_query = query.strip()
    if clean_query.lower().startswith("for "):
        clean_query = clean_query[4:].strip()
    if clean_query.lower().startswith("app "):
        clean_query = clean_query[4:].strip()
    
    # 1. Tap Windows key to trigger Start Menu / Windows Search
    kbd.press("win")
    time.sleep(0.35)  # Fast responsive pause for search bar focus
    
    # 2. Type search query into Windows Search
    kbd.type_text(clean_query)
    time.sleep(0.4)  # Wait for Windows search index to highlight top match
    
    # 3. Press Enter to launch top result if requested
    if press_enter:
        kbd.press("enter")
        return f"Executed Windows button search and launched: {clean_query}"
    
    return f"Opened Windows button search for: {clean_query}"

def browser_search(query: str, engine: str = "google"):
    """Searches using the default browser. Opens the browser directly to Google search results."""
    import webbrowser
    import urllib.parse
    
    clean_query = query.strip()
    for prefix in ("for ", "on google ", "in google ", "google ", "on browser "):
        if clean_query.lower().startswith(prefix):
            clean_query = clean_query[len(prefix):].strip()
            
    encoded = urllib.parse.quote_plus(clean_query)
    if engine.lower() == "bing":
        url = f"https://www.bing.com/search?q={encoded}"
    else:
        url = f"https://www.google.com/search?q={encoded}"
        
    webbrowser.open(url)
    return f"Executed browser Google search for: {clean_query}"

def mouse_access_logic(action: str, amount: int = None, x: int = None, y: int = None):
    """
    Consolidated mouse logic for scrolling, moving, and clicking.
    action can be: 'scroll_down', 'scroll_up', 'move_and_click', 'click_center'
    """
    mouse = MouseController()
    
    if action == "scroll_down":
        clicks = amount if amount else -500
        mouse.scroll(clicks) # Negative is down in Windows usually
        return f"Scrolled down by {clicks} units."
        
    elif action == "scroll_up":
        clicks = amount if amount else 500
        mouse.scroll(clicks)
        return f"Scrolled up by {clicks} units."
        
    elif action == "move_and_click":
        if x is None or y is None:
            return "Error: x and y coordinates required for move_and_click."
        mouse.move(x, y)
        time.sleep(0.2)
        mouse.click(button="left")
        return f"Moved mouse to ({x}, {y}) and clicked."
        
    elif action == "click_center":
        # Click wherever the mouse currently is (e.g. after a UIA move)
        mouse.click(button="left")
        return "Clicked at current mouse location."
        
    return f"Unknown mouse action: {action}"

SHORTCUT_MAP = {
    # Tab Management
    "new tab": ["ctrl", "t"],
    "close tab": ["ctrl", "w"],
    "reopen tab": ["ctrl", "shift", "t"],
    "reopen closed tab": ["ctrl", "shift", "t"],
    "next tab": ["ctrl", "tab"],
    "previous tab": ["ctrl", "shift", "tab"],
    "prev tab": ["ctrl", "shift", "tab"],
    "tab 1": ["ctrl", "1"],
    "tab 2": ["ctrl", "2"],
    "tab 3": ["ctrl", "3"],
    "tab 4": ["ctrl", "4"],
    "tab 5": ["ctrl", "5"],
    "tab 6": ["ctrl", "6"],
    "tab 7": ["ctrl", "7"],
    "tab 8": ["ctrl", "8"],
    "first tab": ["ctrl", "1"],
    "last tab": ["ctrl", "9"],

    # Navigation & Page Control
    "back": ["alt", "left"],
    "go back": ["alt", "left"],
    "previous page": ["alt", "left"],
    "forward": ["alt", "right"],
    "go forward": ["alt", "right"],
    "next page": ["alt", "right"],
    "refresh": ["ctrl", "r"],
    "reload": ["ctrl", "r"],
    "hard refresh": ["ctrl", "f5"],
    "force refresh": ["ctrl", "f5"],
    "stop loading": ["esc"],
    "stop": ["esc"],
    "fullscreen": ["f11"],
    "full screen": ["f11"],

    # Search & Zoom
    "find": ["ctrl", "f"],
    "find text": ["ctrl", "f"],
    "search page": ["ctrl", "f"],
    "search bar": ["ctrl", "k"],
    "browser search bar": ["ctrl", "k"],
    "focus search bar": ["ctrl", "k"],
    "address bar": ["ctrl", "l"],
    "focus address bar": ["ctrl", "l"],
    "zoom in": ["ctrl", "+"],
    "zoom out": ["ctrl", "-"],
    "reset zoom": ["ctrl", "0"],

    # History, Bookmarks & System
    "downloads": ["ctrl", "j"],
    "history": ["ctrl", "h"],
    "bookmark": ["ctrl", "d"],
    "bookmark page": ["ctrl", "d"],
    "incognito": ["ctrl", "shift", "n"],
    "private window": ["ctrl", "shift", "n"],

    # Media & Play/Pause
    "play": ["space"],
    "pause": ["space"],
    "play pause": ["space"],
    "play/pause": ["space"],
    "mute video": ["m"],

    # OS & Window Shortcuts
    "window": ["win"],
    "windows": ["win"],
    "start menu": ["win"],
    "task manager": ["ctrl", "shift", "esc"],
    "close window": ["alt", "f4"],
    "desktop": ["win", "d"],
    "show desktop": ["win", "d"],
    "file explorer": ["win", "e"],
    "explorer": ["win", "e"],
    "settings": ["win", "i"],
    "lock screen": ["win", "l"],
    "lock": ["win", "l"],
    "screenshot": ["win", "shift", "s"],
    "snip": ["win", "shift", "s"],
    "action center": ["win", "a"],
    "notifications": ["win", "n"],
    "switch window": ["alt", "tab"],
    "switch app": ["alt", "tab"],

    # Editing & Clipboard Shortcuts
    "copy": ["ctrl", "c"],
    "paste": ["ctrl", "v"],
    "cut": ["ctrl", "x"],
    "undo": ["ctrl", "z"],
    "redo": ["ctrl", "y"],
    "save": ["ctrl", "s"],
    "select all": ["ctrl", "a"],
    "print": ["ctrl", "p"],
}

def execute_mapped_shortcut(action: str):
    """Executes a predefined keyboard shortcut based on a semantic name."""
    action_lower = action.lower().strip()
    if action_lower not in SHORTCUT_MAP:
        return {"success": False, "error": f"Shortcut '{action}' not found in engine map."}

    keys = SHORTCUT_MAP[action_lower]
    kbd = KeyboardController()

    try:
        if len(keys) == 1:
            kbd.press(keys[0])
        else:
            kbd.hotkey(*keys)
        return {"success": True, "message": f"Executed shortcut '{action_lower}' using keys: {' + '.join(keys)}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_current_desktop_state():
    """Detect current active desktop, active window, whether it's a browser/desktop/whatsapp, and context shortcuts."""
    import ctypes
    from ctypes import wintypes
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            hwnd = user32.GetDesktopWindow()

        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, len(buf))
        title = buf.value or "Desktop"

        # Get class name
        class_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_buf, 256)
        class_name = class_buf.value or ""

        # Get process ID and name
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        process_name = ""
        try:
            import psutil
            process_name = psutil.Process(pid.value).name().lower()
        except Exception:
            pass

        title_lower = title.lower()
        is_browser = (
            any(b in process_name for b in ("chrome", "msedge", "firefox", "brave", "opera", "vivaldi", "browser"))
            or any(b in title_lower for b in ("google chrome", "microsoft edge", "mozilla firefox", "brave", "opera"))
        )
        is_desktop = (
            class_name in ("Progman", "WorkerW")
            or "program manager" in title_lower
            or "desktop" in title_lower
        )
        is_whatsapp = (
            "whatsapp" in process_name
            or "whatsapp" in title_lower
        )

        # Contextual recommended shortcuts based on current state
        if is_browser:
            current_state = "browser"
            recommended_shortcuts = [
                "Ctrl+T (New Tab)", "Ctrl+W (Close Tab)", "Ctrl+Shift+T (Reopen Tab)",
                "Ctrl+K / Ctrl+L (Focus Search/Address Bar)", "Ctrl+R (Refresh)",
                "Ctrl+F (Find Text)", "Ctrl+H (History)", "Ctrl+J (Downloads)",
                "Alt+Left (Back)", "Alt+Right (Forward)", "Ctrl+Tab (Next Tab)",
                "Space (Play/Pause Media)"
            ]
        elif is_whatsapp:
            current_state = "whatsapp"
            recommended_shortcuts = [
                "Ctrl+F (Search Contacts/Chats)", "Enter (Send Message)",
                "Escape (Close Search/Chat)", "Ctrl+N (New Chat)"
            ]
        elif is_desktop:
            current_state = "desktop"
            recommended_shortcuts = [
                "Win (Windows Button Search / Start Menu)", "Win+D (Toggle Desktop)",
                "Win+E (File Explorer)", "Win+I (Settings)", "Alt+Tab (Switch App)",
                "Ctrl+Shift+Esc (Task Manager)"
            ]
        else:
            current_state = f"app:{process_name or title}"
            recommended_shortcuts = [
                "Alt+Tab (Switch App)", "Win+D (Show Desktop)", "Alt+F4 (Close Window)",
                "Ctrl+S (Save)", "Ctrl+Z (Undo)"
            ]

        return {
            "success": True,
            "current_state": current_state,
            "active_window_title": title,
            "active_class_name": class_name,
            "active_process": process_name,
            "is_browser": is_browser,
            "is_desktop": is_desktop,
            "is_whatsapp": is_whatsapp,
            "recommended_shortcuts": recommended_shortcuts,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def browser_search_bar_focus_and_search(query: str = "", click_first_result: bool = False):
    """Focuses the browser search bar via Ctrl+K, types the search query, and optionally clicks the top result."""
    kbd = KeyboardController()
    # 1. Focus search bar with Ctrl + K
    kbd.hotkey("ctrl", "k")
    time.sleep(0.2)

    if query:
        kbd.type_text(query)
        time.sleep(0.15)
        kbd.press("enter")

        if click_first_result:
            time.sleep(1.2)  # Wait for results to render
            # Try to click the first link below using UIA or keyboard navigation
            try:
                from app.tools.uia import uia_detect_elements, uia_click_element
                detected = uia_detect_elements(category="links", max_depth=6)
                if detected.get("success") and detected.get("links"):
                    # First substantive link below search bar
                    first_link = detected["links"][0]
                    return uia_click_element(element_id=first_link.get("element_id"))
            except Exception:
                pass
            # Fallback: Tab down to first result and press enter
            kbd.press("tab")
            time.sleep(0.1)
            kbd.press("enter")

        return {"success": True, "message": f"Focused browser search bar and searched for: {query}"}

    return {"success": True, "message": "Focused browser search bar via Ctrl+K"}


def whatsapp_search_and_message(contact: str, message: str = ""):
    """Automates searching for a contact on WhatsApp, selecting them, and optionally sending a message."""
    # 1. Bring WhatsApp window to focus
    focus_res = window_focus("WhatsApp")
    time.sleep(0.3)

    kbd = KeyboardController()
    # 2. Press Ctrl + F to focus WhatsApp contact search
    kbd.hotkey("ctrl", "f")
    time.sleep(0.2)

    # 3. Type contact name
    kbd.type_text(contact.strip())
    time.sleep(0.6)  # Wait for contacts list to filter

    # 4. Press Down arrow then Enter to select first matched contact
    kbd.press("down")
    time.sleep(0.15)
    kbd.press("enter")
    time.sleep(0.3)

    # 5. If message provided, type message and send
    if message:
        kbd.type_text(message)
        time.sleep(0.2)
        kbd.press("enter")
        return {
            "success": True,
            "message": f"Sent WhatsApp message to '{contact}': {message}",
            "contact": contact,
            "sent_text": message
        }

    return {
        "success": True,
        "message": f"Opened WhatsApp chat for contact: '{contact}'",
        "contact": contact
    }


def uia_click_button_by_semantic_role(role: str, query: str = "", window_title: str = ""):
    """Clicks a button by semantic role ('like', 'send', 'submit', 'enter', 'close', 'box') using UIA."""
    try:
        from app.tools.uia import uia_detect_elements, uia_click_element, uia_detect_box_content, uia_click_inside_box, ensure_com_initialized
        ensure_com_initialized()
        role_lower = role.lower().strip()

        if role_lower in ("like", "like button", "thumbs up"):
            # Search for like button
            detected = uia_detect_elements(window_title=window_title, category="buttons")
            if detected.get("success") and detected.get("buttons"):
                for btn in detected["buttons"]:
                    name_low = (btn.get("name") or "").lower()
                    if "like" in name_low or "thumbs up" in name_low:
                        return uia_click_element(element_id=btn.get("element_id"), window_title=window_title)
            # Fallback: query match
            return uia_click_element(window_title=window_title, query=query or "like")

        elif role_lower in ("send", "send button"):
            detected = uia_detect_elements(window_title=window_title, category="submit_buttons")
            if detected.get("success") and detected.get("submit_buttons"):
                return uia_click_element(element_id=detected["submit_buttons"][0].get("element_id"), window_title=window_title)
            # Fallback: press Enter
            kbd = KeyboardController()
            kbd.press("enter")
            return {"success": True, "message": "Pressed Enter to send."}

        elif role_lower in ("enter", "enter button", "submit", "submit button"):
            detected = uia_detect_elements(window_title=window_title, category="enter_buttons")
            if detected.get("success") and detected.get("enter_buttons"):
                return uia_click_element(element_id=detected["enter_buttons"][0].get("element_id"), window_title=window_title)
            kbd = KeyboardController()
            kbd.press("enter")
            return {"success": True, "message": "Executed enter button."}

        elif role_lower in ("box", "container", "modal", "dialog"):
            box_res = uia_detect_box_content(box_query=query, window_title=window_title)
            return box_res

        # Default: generic query search
        return uia_click_element(window_title=window_title, query=query or role)
    except Exception as e:
        return {"success": False, "error": str(e)}


def click_ui_content(query: str, element_type: str = "any", window_title: str = ""):
    """Finds and clicks any on-screen content area — whether it is a box, text, icon, button, link, or container.
    - query: Content name, quoted text, or label (e.g. '"Search"', 'subscribe', 'settings icon', 'username box').
    - element_type: 'any', 'box', 'text', 'icon', 'button'.
    - window_title: Optional target window title.
    """
    try:
        from app.tools.uia import _get_window, _classify_control, auto, ensure_com_initialized
        ensure_com_initialized()
        from app.tools.computer.mouse import MouseController
        import re

        clean_q = (query or "").strip().strip("\"' ")
        if not clean_q:
            return {"success": False, "error": "No content query specified"}

        # Infer element type from query if not explicitly set
        etype = (element_type or "any").lower().strip()
        low_q = clean_q.lower()

        if etype == "any":
            if any(low_q.startswith(p) for p in ("box ", "input box ", "text box ")) or low_q.endswith(" box"):
                etype = "box"
                clean_q = re.sub(r"^(?:input\s+box|text\s+box|box)\s+|\s+box$", "", clean_q, flags=re.IGNORECASE).strip()
            elif low_q.startswith("icon ") or low_q.endswith(" icon"):
                etype = "icon"
                clean_q = re.sub(r"^icon\s+|\s+icon$", "", clean_q, flags=re.IGNORECASE).strip()
            elif low_q.startswith("text ") or low_q.endswith(" text"):
                etype = "text"
                clean_q = re.sub(r"^text\s+|\s+text$", "", clean_q, flags=re.IGNORECASE).strip()
            elif low_q.startswith("button ") or low_q.endswith(" button"):
                etype = "button"
                clean_q = re.sub(r"^button\s+|\s+button$", "", clean_q, flags=re.IGNORECASE).strip()
            elif "content area" in low_q:
                clean_q = re.sub(r"\bcontent\s+area\b", "", clean_q, flags=re.IGNORECASE).strip()

        clean_q = clean_q.strip("\"' ")
        target_lower = clean_q.lower()

        if not auto:
            return {"success": False, "error": "uiautomation module not available"}

        win = _get_window(window_title)
        best_candidate = None
        best_score = -1

        for control, _ in auto.WalkControl(win, maxDepth=6):
            if not control or control == win:
                continue
            try:
                if control.IsOffscreen:
                    continue
            except Exception:
                pass

            info = _classify_control(control)
            if not info.get("center"):
                continue

            name = (info.get("name") or "").strip()
            name_low = name.lower()
            auto_id = (info.get("automation_id") or "").lower()
            class_name = (info.get("class_name") or "").lower()
            roles = info.get("roles", [])
            family = info.get("control_family", "generic")

            # Check match against target
            match_score = 0
            if target_lower:
                if target_lower == name_low or target_lower == auto_id:
                    match_score = 100
                elif target_lower in name_low:
                    match_score = 80
                elif target_lower in auto_id or target_lower in class_name:
                    match_score = 60
                elif any(word in name_low for word in target_lower.split() if len(word) > 2):
                    match_score = 40
            else:
                match_score = 10

            if match_score == 0:
                continue

            # Type filtering and boosting
            if etype == "box":
                if family == "box" or info.get("is_box") or info.get("is_input_field") or "box" in roles:
                    match_score += 30
                elif "button" in roles:
                    match_score -= 20
            elif etype == "text":
                if family == "text" or info.get("is_text_label") or "text_label" in roles or "link" in roles:
                    match_score += 30
            elif etype == "icon":
                if family == "image" or info.get("is_image") or "image" in roles or "icon" in class_name or "icon" in auto_id:
                    match_score += 30
            elif etype == "button":
                if info.get("is_button") or "button" in roles:
                    match_score += 30
            else:
                # Any: boost clickable elements
                if "clickable" in roles or info.get("is_button") or "link" in roles:
                    match_score += 15

            if match_score > best_score:
                best_score = match_score
                best_candidate = (control, info)

        if best_candidate and best_score > 0:
            ctrl, inf = best_candidate
            cx, cy = inf["center"]["x"], inf["center"]["y"]
            elem_family = inf.get("control_family", "element")
            elem_name = inf.get("name") or clean_q

            # Try invoke pattern if available and it is a button/link
            invoked = False
            if hasattr(ctrl, "InvokePattern") and ctrl.InvokePattern:
                try:
                    ctrl.InvokePattern.Invoke()
                    invoked = True
                except Exception:
                    pass

            if not invoked:
                m_ctrl = MouseController()
                m_ctrl.move(cx, cy, duration=0.15)
                m_ctrl.click(cx, cy)

            return {
                "success": True,
                "message": f"Clicked {elem_family} '{elem_name}' at ({cx}, {cy})",
                "center": {"x": cx, "y": cy},
                "element_type": elem_family,
                "name": elem_name,
                "score": best_score
            }

        return {
            "success": False,
            "error": f"Could not find UI content area matching '{clean_q}' (searched box, text, icon, button)."
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def click_first_link_below(window_title: str = ""):
    """Finds and clicks the first link, video thumbnail, or search result below the header/search bar."""
    time.sleep(0.3)
    # 1. Try UIA to find links or clickable text in the content area
    try:
        from app.tools.uia import uia_detect_elements, uia_click_element, ensure_com_initialized
        ensure_com_initialized()
        res = uia_detect_elements(window_title=window_title, category="all", max_depth=6)
        if res.get("success"):
            candidates = res.get("links", []) + [
                e for e in res.get("clickable", [])
                if e.get("control_type") in ("HyperlinkControl", "TextControl", "GroupControl", "ButtonControl")
            ]
            # Filter elements located below the browser address/toolbar (top > 130 and top < 650)
            below_links = [
                c for c in candidates
                if c.get("bounding_box") and c["bounding_box"]["top"] >= 130 and c["bounding_box"]["top"] <= 650 and c["bounding_box"]["left"] >= 60
            ]
            if below_links:
                first = below_links[0]
                click_res = uia_click_element(window_title=window_title, element_id=first.get("element_id"))
                if click_res.get("success"):
                    return {"success": True, "message": f"Clicked first link below: '{first.get('name', 'link')}'", "details": click_res}
    except Exception:
        pass

    # 2. Viewport coordinate click based on active window coordinates
    try:
        import ctypes
        from ctypes import wintypes
        import pyautogui
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        rect = wintypes.RECT()
        if hwnd and user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            win_left = rect.left
            win_top = rect.top
            win_w = rect.right - rect.left
            win_h = rect.bottom - rect.top
        else:
            win_left, win_top = 0, 0
            win_w, win_h = pyautogui.size()

        # In YouTube and Google Search, the first video/result sits around 38% across and 32% down
        target_x = win_left + int(win_w * 0.38)
        target_y = win_top + int(win_h * 0.32)

        pyautogui.moveTo(target_x, target_y, duration=0.2)
        pyautogui.click(target_x, target_y)
        return {"success": True, "message": f"Automated click on first result link below search bar at ({target_x}, {target_y})"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _fetch_youtube_first_video_id(query: str):
    """Fetch the first video ID for a query from YouTube search results in background."""
    import urllib.request
    import urllib.parse
    import re
    try:
        url = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(query)}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        )
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            # Extract video ID
            m = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
            if m:
                return m[0]
            m2 = re.findall(r'/watch\?v=([a-zA-Z0-9_-]{11})', html)
            if m2:
                return m2[0]
    except Exception:
        pass
    return None


def play_music_or_media(query: str = "", platform: str = "youtube"):
    """Plays music or media. If query is empty, toggles play/pause on active media.
    If query is provided:
    - Default platform: YouTube (direct video play via video ID, or search + auto-click first video).
    - Optional platforms: Hotstar / JioCinema / JioHotstar, Spotify, Netflix, Prime Video, Soundcloud.
    """
    clean = (query or "").strip()
    import re
    clean = re.sub(r"^(?:the\s+)?(?:song\s+|music\s+|track\s+|video\s+|movie\s+|match\s+)?", "", clean, flags=re.IGNORECASE).strip()

    if not clean or clean.lower() in ("song", "music", "pause", "resume", "media"):
        try:
            import pyautogui
            pyautogui.press("playpause")
            return {"success": True, "message": "Toggled media Play/Pause."}
        except Exception:
            return execute_mapped_shortcut("play")

    import webbrowser
    import urllib.parse

    plat = (platform or "youtube").lower().strip()
    clean_lower = clean.lower()

    # Detect platform from query if mentioned in text
    if any(k in clean_lower for k in ("hotstar", "hostar", "jiohotstar", "jiohostar", "jio hotstar", "jio hostar", "jio cinema", "jiocinema")) or plat in ("hotstar", "hostar", "jiohotstar", "jio", "jiocinema"):
        plat = "hotstar"
        clean = re.sub(r"\b(?:on\s+)?(?:jio\s*hott?star|hott?star|jio\s*cinema|jiocinema)\b", "", clean, flags=re.IGNORECASE).strip()
    elif "spotify" in clean_lower or plat == "spotify":
        plat = "spotify"
        clean = re.sub(r"\b(?:on\s+)?spotify\b", "", clean, flags=re.IGNORECASE).strip()
    elif "netflix" in clean_lower or plat == "netflix":
        plat = "netflix"
        clean = re.sub(r"\b(?:on\s+)?netflix\b", "", clean, flags=re.IGNORECASE).strip()
    elif any(k in clean_lower for k in ("prime video", "prime", "amazon prime")) or plat in ("prime", "amazon"):
        plat = "prime"
        clean = re.sub(r"\b(?:on\s+)?(?:amazon\s+)?prime(?:\s+video)?\b", "", clean, flags=re.IGNORECASE).strip()
    elif "soundcloud" in clean_lower or plat == "soundcloud":
        plat = "soundcloud"
        clean = re.sub(r"\b(?:on\s+)?soundcloud\b", "", clean, flags=re.IGNORECASE).strip()
    elif "youtube" in clean_lower or "yt" in clean_lower:
        plat = "youtube"
        clean = re.sub(r"\b(?:on\s+)?(?:youtube|yt)\b", "", clean, flags=re.IGNORECASE).strip()

    encoded = urllib.parse.quote_plus(clean)

    if plat == "hotstar":
        url = f"https://www.hotstar.com/in/explore?search_query={encoded}"
        webbrowser.open(url)
        return {"success": True, "message": f"Opened JioHotstar for '{clean}'", "platform": "hotstar", "url": url}

    elif plat == "spotify":
        url = f"https://open.spotify.com/search/{encoded}"
        webbrowser.open(url)
        return {"success": True, "message": f"Opened Spotify for '{clean}'", "platform": "spotify", "url": url}

    elif plat == "netflix":
        url = f"https://www.netflix.com/search?q={encoded}"
        webbrowser.open(url)
        return {"success": True, "message": f"Opened Netflix for '{clean}'", "platform": "netflix", "url": url}

    elif plat == "prime":
        url = f"https://www.primevideo.com/search/ref=atv_nb_sr?phrase={encoded}"
        webbrowser.open(url)
        return {"success": True, "message": f"Opened Prime Video for '{clean}'", "platform": "prime", "url": url}

    elif plat == "soundcloud":
        url = f"https://soundcloud.com/search?q={encoded}"
        webbrowser.open(url)
        return {"success": True, "message": f"Opened SoundCloud for '{clean}'", "platform": "soundcloud", "url": url}

    # Default: YouTube with direct video play
    video_id = _fetch_youtube_first_video_id(clean)
    if video_id:
        direct_url = f"https://www.youtube.com/watch?v={video_id}"
        webbrowser.open(direct_url)
        return {"success": True, "message": f"Playing '{clean}' directly on YouTube", "platform": "youtube", "url": direct_url, "video_id": video_id}

    # Fallback to search results + auto-click first link below
    search_url = f"https://www.youtube.com/results?search_query={encoded}"
    webbrowser.open(search_url)
    time.sleep(2.0)
    click_res = click_first_link_below()
    return {
        "success": True,
        "message": f"Searched '{clean}' on YouTube and automatically clicked the first video link below",
        "platform": "youtube",
        "url": search_url,
        "click_status": click_res
    }

