"""
action_patterns.py – Universal User Action Patterns for JARVIS
=============================================================
Matches the mental model and physical patterns of human computer interaction:
  1. Search & Navigate (browsers, desktop apps, Start menu, File Explorer)
  2. Form Fill & Submit (login, settings, multi-field inputs)
  3. Dialog & Decision Handling (OK, Cancel, Save, Don't Save, dismiss)
  4. Tab & Window Orchestration (new tab, close tab, switch, minimize, maximize)
  5. Scroll & Discover (viewport scanning and downward/upward scrolling)
  6. Context Menu & Selection (right-click, menu inspection, action selection)
  7. Smart Click or Type (universal target-aware element handler)
"""

import time
import re
from typing import Dict, Any, Optional, List

from app.tools.computer.keyboard import KeyboardController
from app.tools.computer.mouse import MouseController


def _get_active_window_info() -> Dict[str, Any]:
    """Retrieve title and process info of current active/foreground window using fast Win32 APIs first."""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if hwnd and user32.IsWindow(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            title = ""
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, len(buf))
                title = buf.value or ""
            class_buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_buf, 256)
            return {
                "title": title,
                "class_name": class_buf.value or "",
                "handle": int(hwnd)
            }
    except Exception:
        pass

    try:
        import ctypes
        ctypes.windll.ole32.CoInitialize(None)
        import uiautomation as auto
        fg = auto.GetForegroundControl()
        if fg:
            return {
                "title": getattr(fg, "Name", "") or "",
                "class_name": getattr(fg, "ClassName", "") or "",
                "handle": getattr(fg, "NativeWindowHandle", 0) or 0
            }
    except Exception:
        pass
    return {"title": "active", "class_name": "", "handle": 0}


def pattern_search_and_navigate(
    query: str,
    window_title: str = "active",
    submit: bool = True
) -> Dict[str, Any]:
    """
    Pattern 1: Search & Navigate
    Matches human habit: locate search bar / address bar, clear, type query, and submit.
    Cascades: Browser hotkey (Ctrl+L) -> UIA Search Bar -> Shortcut fallback (Ctrl+F / Win).
    """
    kbd = KeyboardController()
    mouse = MouseController()
    query = (query or "").strip()
    if not query:
        return {"success": False, "error": "Query cannot be empty."}

    win_info = _get_active_window_info()
    title_lower = (win_info.get("title") or "").lower()
    is_browser = any(b in title_lower for b in ("chrome", "edge", "firefox", "brave", "opera", "browser"))

    # 1. Browser accelerator: Ctrl+L focuses address/search bar directly
    if is_browser:
        try:
            kbd.hotkey("ctrl", "l")
            time.sleep(0.15)
            kbd.type_text(query)
            if submit:
                time.sleep(0.1)
                kbd.press("enter")
            return {
                "success": True,
                "pattern": "search_and_navigate",
                "method": "browser_address_bar",
                "query": query,
                "submitted": submit
            }
        except Exception as e:
            pass

    # 2. Semantic UIA Search Bar detection
    try:
        from app.tools.uia import uia_detect_elements
        det = uia_detect_elements(window_title=window_title, category="search_bars", max_depth=4)
        bars = det.get("search_bars", [])
        if bars:
            target = bars[0]
            center = target.get("center")
            if center:
                mouse.click(center["x"], center["y"])
                time.sleep(0.15)
                # Select all and type
                kbd.hotkey("ctrl", "a")
                time.sleep(0.05)
                kbd.type_text(query)
                if submit:
                    time.sleep(0.1)
                    kbd.press("enter")
                return {
                    "success": True,
                    "pattern": "search_and_navigate",
                    "method": "uia_search_bar",
                    "target_name": target.get("name"),
                    "coordinates": center,
                    "query": query,
                    "submitted": submit
                }
    except Exception:
        pass

    # 3. In-App Find fallback (Ctrl+F)
    try:
        kbd.hotkey("ctrl", "f")
        time.sleep(0.15)
        kbd.type_text(query)
        if submit:
            time.sleep(0.1)
            kbd.press("enter")
        return {
            "success": True,
            "pattern": "search_and_navigate",
            "method": "shortcut_find_fallback",
            "query": query,
            "submitted": submit
        }
    except Exception as e:
        return {"success": False, "error": f"Search pattern failed: {e}"}


def pattern_form_fill_and_submit(
    fields: Dict[str, str],
    submit_button: str = "",
    window_title: str = "active"
) -> Dict[str, Any]:
    """
    Pattern 2: Form Fill & Submit
    Sequentially matches labels/fields, focuses each input, types values, and clicks submit.
    """
    if not isinstance(fields, dict) or not fields:
        return {"success": False, "error": "fields must be a non-empty dictionary of field_name -> value."}

    from app.tools.uia import uia_type_into_element, uia_click_element
    filled = []
    failed = []

    for label, val in fields.items():
        res = uia_type_into_element(window_title=window_title, query=str(label), text=str(val))
        if res.get("success"):
            filled.append(label)
        else:
            failed.append(label)
        time.sleep(0.2)

    submit_res = None
    if submit_button:
        time.sleep(0.3)
        submit_res = uia_click_element(window_title=window_title, query=submit_button)
    elif any(k in filled for k in fields.keys()):
        # Try to find a default affirmative button if user didn't specify one
        from app.tools.uia import uia_detect_elements
        det = uia_detect_elements(window_title=window_title, category="submit_buttons", max_depth=4)
        submits = det.get("submit_buttons", [])
        if submits:
            target = submits[0]
            submit_res = uia_click_element(window_title=window_title, query=target.get("name", ""))

    return {
        "success": len(filled) > 0,
        "pattern": "form_fill_and_submit",
        "filled_fields": filled,
        "failed_fields": failed,
        "submitted": submit_res.get("success", False) if submit_res else False
    }


def _verify_and_recover_dialog(initial_hwnd: int, decision: str, kbd: KeyboardController) -> Dict[str, Any]:
    """Verify dialog dismissed; if still visible after 150ms, fire keyboard recovery."""
    verified = True
    recovery_invoked = False
    if initial_hwnd:
        try:
            import ctypes
            user32 = ctypes.windll.user32
            time.sleep(0.15)
            if user32.IsWindow(initial_hwnd) and user32.IsWindowVisible(initial_hwnd):
                # Dialog still present, attempt keyboard recovery
                recovery_invoked = True
                if decision == "affirmative":
                    kbd.press("enter")
                else:
                    kbd.press("esc")
                time.sleep(0.1)
                still_open = bool(user32.IsWindow(initial_hwnd) and user32.IsWindowVisible(initial_hwnd))
                verified = not still_open
        except Exception:
            pass
    return {"verified": verified, "recovery_invoked": recovery_invoked}


def pattern_handle_dialog(
    decision: str = "affirmative",
    window_title: str = "active"
) -> Dict[str, Any]:
    """
    Pattern 3: Dialog & Decision Handling
    Human decision mapping:
      - 'affirmative': OK, Save, Yes, Confirm, Allow, Continue
      - 'negative': Cancel, No, Don't Save, Deny, Discard
      - 'close': Close (X), Dismiss
    Includes post-action verification and state delta recovery.
    """
    decision = (decision or "affirmative").lower()
    kbd = KeyboardController()
    win_info = _get_active_window_info()
    initial_hwnd = win_info.get("handle") or 0

    from app.tools.uia import uia_detect_elements, uia_click_element

    affirmative_labels = ("ok", "save", "yes", "confirm", "allow", "continue", "done", "apply")
    negative_labels = ("cancel", "no", "don't save", "dont save", "deny", "discard", "abort")

    if decision == "close":
        # Look for close button first
        det = uia_detect_elements(window_title=window_title, category="close_buttons", max_depth=3)
        closes = det.get("close_buttons", [])
        if closes:
            target = closes[0]
            res = uia_click_element(window_title=window_title, query=target.get("name") or "Close")
            if res.get("success"):
                verification = _verify_and_recover_dialog(initial_hwnd, decision, kbd)
                return {
                    "success": True,
                    "pattern": "handle_dialog",
                    "decision": decision,
                    "action": "clicked_close_button",
                    **verification
                }
        kbd.press("esc")
        verification = _verify_and_recover_dialog(initial_hwnd, decision, kbd)
        return {
            "success": True,
            "pattern": "handle_dialog",
            "decision": decision,
            "action": "sent_escape_key",
            **verification
        }

    target_labels = affirmative_labels if decision == "affirmative" else negative_labels

    # Scan buttons
    det = uia_detect_elements(window_title=window_title, category="buttons", max_depth=3)
    buttons = det.get("buttons", [])
    for btn in buttons:
        btn_name = (btn.get("name") or "").lower()
        if any(lbl in btn_name for lbl in target_labels):
            res = uia_click_element(window_title=window_title, query=btn.get("name", ""))
            if res.get("success"):
                verification = _verify_and_recover_dialog(initial_hwnd, decision, kbd)
                return {
                    "success": True,
                    "pattern": "handle_dialog",
                    "decision": decision,
                    "target": btn.get("name"),
                    **verification
                }

    # Keyboard fallback
    if decision == "affirmative":
        kbd.press("enter")
        action_name = "pressed_enter"
    else:
        kbd.press("esc")
        action_name = "pressed_escape"

    verification = _verify_and_recover_dialog(initial_hwnd, decision, kbd)
    return {
        "success": True,
        "pattern": "handle_dialog",
        "decision": decision,
        "action": action_name,
        **verification
    }


def pattern_tab_and_window(
    action: str,
    target: str = ""
) -> Dict[str, Any]:
    """
    Pattern 4: Tab & Window Orchestration
    Supported actions:
      'new_tab', 'close_tab', 'next_tab', 'prev_tab',
      'minimize', 'maximize', 'restore', 'close_window'
    """
    kbd = KeyboardController()
    action = (action or "").lower().replace(" ", "_").replace("-", "_")

    actions_map = {
        "new_tab": ("ctrl", "t"),
        "close_tab": ("ctrl", "w"),
        "reopen_tab": ("ctrl", "shift", "t"),
        "next_tab": ("ctrl", "tab"),
        "prev_tab": ("ctrl", "shift", "tab"),
        "previous_tab": ("ctrl", "shift", "tab"),
        "close_window": ("alt", "f4"),
        "minimize": ("win", "down"),
        "maximize": ("win", "up"),
    }

    if action in actions_map:
        keys = actions_map[action]
        if len(keys) == 1:
            kbd.press(keys[0])
        elif len(keys) == 2:
            kbd.hotkey(keys[0], keys[1])
        elif len(keys) == 3:
            kbd.hotkey(keys[0], keys[1], keys[2])
        return {"success": True, "pattern": "tab_and_window", "action": action}

    return {"success": False, "error": f"Unsupported action '{action}'. Valid: {list(actions_map.keys())}"}


def pattern_scroll_and_find(
    target_text: str,
    max_scrolls: int = 5,
    direction: str = "down",
    window_title: str = "active"
) -> Dict[str, Any]:
    """
    Pattern 5: Scroll & Discover
    Repeatedly checks if an element is visible; scrolls viewport until located.
    """
    from app.tools.uia import uia_find, uia_get_element_location
    mouse = MouseController()

    target_text = (target_text or "").strip()
    if not target_text:
        return {"success": False, "error": "target_text cannot be empty."}

    clicks = -5 if direction.lower() == "down" else 5

    for attempt in range(max_scrolls + 1):
        loc = uia_get_element_location(window_title=window_title, query=target_text)
        if loc.get("success") and loc.get("center"):
            return {
                "success": True,
                "pattern": "scroll_and_find",
                "target": target_text,
                "found_on_attempt": attempt,
                "location": loc.get("location"),
                "center": loc.get("center")
            }

        if attempt < max_scrolls:
            mouse.scroll(clicks)
            time.sleep(0.3)

    return {
        "success": False,
        "pattern": "scroll_and_find",
        "error": f"Element '{target_text}' not found after {max_scrolls} scrolls {direction}."
    }


def pattern_context_action(
    x: Optional[int] = None,
    y: Optional[int] = None,
    target_element: str = "",
    menu_item: str = "",
    window_title: str = "active"
) -> Dict[str, Any]:
    """
    Pattern 6: Context Menu & Selection
    Right-clicks an element or coordinate, opens context menu, and selects an option.
    """
    mouse = MouseController()
    kbd = KeyboardController()

    # Determine coordinates
    if x is None or y is None:
        if target_element:
            from app.tools.uia import uia_get_element_location
            loc = uia_get_element_location(window_title=window_title, query=target_element)
            center = loc.get("center")
            if center:
                x, y = center["x"], center["y"]

    if x is None or y is None:
        # Use current mouse location
        pos = mouse.position()
        x, y = pos[0], pos[1]

    # Perform right-click
    mouse.click(x, y, button="right")
    time.sleep(0.2)

    # If menu item specified, try to find and click it or use arrow keys
    if menu_item:
        try:
            from app.tools.uia import uia_click_element
            res = uia_click_element(window_title=window_title, query=menu_item)
            if res.get("success"):
                return {"success": True, "pattern": "context_action", "menu_item": menu_item, "method": "uia_menu_click"}
        except Exception:
            pass
        # Fallback: type initial letter or down arrow + enter
        kbd.press("down")
        time.sleep(0.1)
        kbd.press("enter")
        return {"success": True, "pattern": "context_action", "menu_item": menu_item, "method": "keyboard_select"}

    return {"success": True, "pattern": "context_action", "right_clicked_at": {"x": x, "y": y}}


def pattern_smart_click_or_type(
    target: str,
    text: str = "",
    window_title: str = "active"
) -> Dict[str, Any]:
    """
    Pattern 7: Smart Click or Type
    Universal human intention handler:
      - If text is provided: User wants to input text into target (detects, focuses, types).
      - If text is empty: User wants to click target (detects, clicks center or invokes).
      - Multi-tiered fallbacks:
        Tier 1: Fast UIA element location/type/click
        Tier 2: High-speed OpenCV visual template matching (if target is image path or UIA reports accessibility_blind)
    """
    target = (target or "").strip()
    if not target:
        return {"success": False, "error": "Target element name or description is required."}

    from app.tools.uia import uia_click_element, uia_type_into_element

    # 1. Tier-1 UIA attempt
    if text:
        res = uia_type_into_element(window_title=window_title, query=target, text=text)
        pattern_mode = "smart_type"
    else:
        res = uia_click_element(window_title=window_title, query=target)
        pattern_mode = "smart_click"

    # If UIA succeeded, return directly
    if res.get("success"):
        ret = {
            "success": True,
            "pattern": pattern_mode,
            "target": target,
            "method": "uia",
            "details": res
        }
        if text:
            ret["text"] = text
        return ret

    # 2. Tier-2 Visual Template Matching Fallback
    is_img_path = any(target.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".bmp"))
    is_blind = res.get("reason") == "accessibility_blind" or res.get("accessibility_blind") is True

    if is_img_path or is_blind:
        try:
            from app.tools.vision import vision_match_template
            if is_img_path:
                v_res = vision_match_template(template_path=target, confidence=0.8)
                if v_res.get("found"):
                    mouse = MouseController()
                    mouse.click(v_res["center_x"], v_res["center_y"])
                    time.sleep(0.15)
                    if text:
                        kbd = KeyboardController()
                        kbd.type_text(text)
                    ret = {
                        "success": True,
                        "pattern": pattern_mode,
                        "target": target,
                        "method": "vision_template_matching",
                        "visual_match": v_res
                    }
                    if text:
                        ret["text"] = text
                    return ret
        except Exception:
            pass

    ret = {
        "success": False,
        "pattern": pattern_mode,
        "target": target,
        "details": res
    }
    if text:
        ret["text"] = text
    if is_blind:
        ret["accessibility_blind"] = True
        ret["escalate_to_vision"] = True
    return ret
