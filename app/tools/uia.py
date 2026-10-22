import traceback
import json
import uuid
import re
import threading
import ctypes
from typing import Optional, Dict, Any, List

_com_local = threading.local()

def ensure_com_initialized():
    """Ensure COM apartment and UIAutomation are initialized on current thread."""
    if not getattr(_com_local, "initialized", False):
        try:
            ctypes.windll.ole32.CoInitialize(None)
        except Exception:
            pass
        try:
            import uiautomation as auto_mod
            if hasattr(auto_mod, "UIAutomationInitializerInThread"):
                _com_local.uia_init = auto_mod.UIAutomationInitializerInThread()
        except Exception:
            pass
        _com_local.initialized = True

# Initialize COM on current thread upon module load
ensure_com_initialized()

# In-memory mapping of element_id -> uiautomation Control
_ui_elements_cache = {}

try:
    import uiautomation as auto
    if auto:
        # Bounded search timeout to prevent UIA hangs on missing controls
        auto.SetGlobalSearchTimeout(2.0)
except ImportError:
    auto = None


def _get_window(window_title: str = ""):
    """Find a target window with tolerant matching (exact, substring, active foreground)."""
    ensure_com_initialized()
    if not auto:
        raise ImportError("uiautomation module is not installed")
    
    clean_title = (window_title or "").strip()
    
    # 1. If no title or 'active' / 'foreground' requested, find active window
    if not clean_title or clean_title.lower() in ("active", "foreground", "current"):
        try:
            # Fast native check: verify foreground window handle is valid first
            import ctypes
            user32 = ctypes.windll.user32
            fg_hwnd = user32.GetForegroundWindow()
            if fg_hwnd and user32.IsWindow(fg_hwnd):
                win_ctrl = auto.ControlFromHandle(fg_hwnd)
                if win_ctrl and win_ctrl.ControlTypeName == "WindowControl":
                    return win_ctrl
        except Exception:
            pass

        try:
            fg = auto.GetForegroundControl()
            if fg:
                curr = fg
                while curr and curr.ControlTypeName != "WindowControl" and curr.GetParentControl():
                    curr = curr.GetParentControl()
                if curr and curr.ControlTypeName == "WindowControl":
                    return curr
        except Exception:
            pass
        # Fallback to first visible top-level window
        for win in auto.GetRootControl().GetChildren():
            if win.ControlTypeName == "WindowControl" and win.Name and not win.IsOffscreen:
                return win

    # 2. Exact match
    win = auto.WindowControl(searchDepth=1, Name=clean_title)
    if win.Exists(0, 0):
        return win
        
    # 3. Substring match
    win_sub = auto.WindowControl(searchDepth=1, SubName=clean_title)
    if win_sub.Exists(0, 0):
        return win_sub

    # 4. Case-insensitive substring search across all root window children
    lowered = clean_title.lower()
    for child in auto.GetRootControl().GetChildren():
        if child.ControlTypeName == "WindowControl" and child.Name:
            if lowered in child.Name.lower():
                return child
                
    raise ValueError(f"Window matching '{window_title}' not found.")


def is_window_accessibility_blind(win_ctrl) -> bool:
    """Detect if window is an ungrounded Canvas / DirectX / OpenGL pane with no accessible semantic UIA nodes (FastCUA paradigm)."""
    if not win_ctrl:
        return True
    try:
        children = win_ctrl.GetChildren()
        if not children:
            return True
        if len(children) <= 2:
            for c in children:
                ctype = str(getattr(c, "ControlTypeName", "") or "")
                if ctype not in ("PaneControl", "CustomControl", "WindowControl"):
                    return False
                cname = getattr(c, "Name", "")
                if cname and isinstance(cname, str) and cname.strip():
                    return False
                auto_id = getattr(c, "AutomationId", "")
                if auto_id and isinstance(auto_id, str) and auto_id.strip():
                    return False
            return True
    except Exception:
        pass
    return False


def _extract_bounding_box_and_center(control):
    """Safely extract bounding box and center coordinate (x, y) from a UIA control."""
    bounding_box = None
    center = None
    try:
        rect = control.BoundingRectangle
        if rect and (rect.width() > 0 or rect.height() > 0):
            bounding_box = {
                "left": int(rect.left),
                "top": int(rect.top),
                "right": int(rect.right),
                "bottom": int(rect.bottom),
                "width": int(rect.width()),
                "height": int(rect.height())
            }
            center = {
                "x": int(rect.xcenter()),
                "y": int(rect.ycenter())
            }
    except Exception:
        pass
    return bounding_box, center


def _classify_control(control) -> Dict[str, Any]:
    """Classify a UIA control into semantic roles (buttons, search bars, inputs, etc.)."""
    ctype = getattr(control, "ControlTypeName", "") or ""
    name = (getattr(control, "Name", "") or "").strip()
    auto_id = (getattr(control, "AutomationId", "") or "").strip()
    class_name = (getattr(control, "ClassName", "") or "").strip()
    
    bbox, center = _extract_bounding_box_and_center(control)
    combined = f"{name} {auto_id} {class_name}".lower()

    is_button = ctype in ("ButtonControl", "SplitButtonControl") or "button" in class_name.lower()
    is_search_bar = (
        ("search" in combined or "find" in combined or "query" in combined)
        and (ctype in ("EditControl", "ComboBoxControl", "TextControl", "GroupControl", "PaneControl") or "search" in combined)
    )
    is_input_field = ctype in ("EditControl", "DocumentControl") or (ctype == "ComboBoxControl" and "search" not in combined)
    
    is_close_button = is_button and any(k in combined for k in ("close", "exit", "cancel", "dismiss", "sysclose"))
    is_submit_button = is_button and any(k in combined for k in ("submit", "send", "confirm", "ok", "done", "save", "apply", "login", "sign in"))
    is_skip_button = is_button and any(k in combined for k in ("skip", "skip ad", "skip intro", "skip video", "remind me later", "not now", "later"))
    is_enter_button = is_button and any(k in combined for k in ("enter", "next", "continue", "proceed", "forward", "go", "start"))
    is_minimize_button = is_button and "minimize" in combined
    is_maximize_button = is_button and any(k in combined for k in ("maximize", "restore"))
    
    is_checkbox = ctype == "CheckBoxControl" or "check" in class_name.lower()
    is_radio = ctype == "RadioButtonControl" or "radio" in class_name.lower()
    is_combobox = ctype in ("ComboBoxControl", "DropDownControl") or "combobox" in class_name.lower()
    is_list_item = ctype in ("ListItemControl", "ListBoxControl") or "list" in class_name.lower()
    is_menu_item = ctype in ("MenuItemControl", "MenuControl", "MenuBarControl") or "menu" in class_name.lower()
    is_tab = ctype in ("TabItemControl", "TabControl") or "tab" in class_name.lower()
    is_link = ctype == "HyperlinkControl" or "link" in class_name.lower()
    is_slider = ctype == "SliderControl" or "slider" in class_name.lower()
    is_progress_bar = ctype == "ProgressBarControl" or "progress" in class_name.lower()
    is_tree_item = ctype in ("TreeItemControl", "TreeControl") or "tree" in class_name.lower()
    is_table = ctype in ("TableControl", "DataGridControl", "DataItemControl", "HeaderControl", "HeaderItemControl") or "grid" in class_name.lower()
    is_image = ctype == "ImageControl" or "image" in class_name.lower() or "icon" in class_name.lower()
    is_text_label = ctype == "TextControl" and not is_search_bar
    is_spinner = ctype == "SpinnerControl" or "spinner" in class_name.lower()
    is_calendar = ctype in ("CalendarControl", "DatePickerControl") or "calendar" in class_name.lower()
    is_tooltip = ctype == "ToolTipControl" or "tooltip" in class_name.lower()
    is_scrollbar = ctype in ("ScrollBarControl", "ThumbControl")
    is_box = ctype in ("PaneControl", "GroupControl", "WindowControl", "CustomControl", "DialogControl") or any(
        k in combined for k in ("box", "card", "container", "modal", "dialog", "popup", "panel", "banner", "toast", "ad")
    )

    is_clickable = (
        is_button or is_link or is_tab or is_menu_item or is_checkbox or
        is_radio or is_list_item or is_tree_item or is_combobox or is_slider or
        ctype in ("HyperlinkControl", "MenuItemControl", "TabItemControl", "CheckBoxControl", "RadioButtonControl", "ListItemControl")
    )

    # Determine primary control family
    if is_button: control_family = "button"
    elif is_search_bar: control_family = "search_bar"
    elif is_combobox: control_family = "combobox"
    elif is_input_field: control_family = "input"
    elif is_checkbox: control_family = "checkbox"
    elif is_radio: control_family = "radio"
    elif is_list_item: control_family = "list"
    elif is_menu_item: control_family = "menu"
    elif is_tab: control_family = "tab"
    elif is_link: control_family = "link"
    elif is_slider: control_family = "slider"
    elif is_progress_bar: control_family = "progress"
    elif is_tree_item: control_family = "tree"
    elif is_table: control_family = "table"
    elif is_image: control_family = "image"
    elif is_text_label: control_family = "text"
    elif is_spinner: control_family = "spinner"
    elif is_calendar: control_family = "calendar"
    elif is_tooltip: control_family = "tooltip"
    elif is_scrollbar: control_family = "scrollbar"
    elif is_box: control_family = "box"
    else: control_family = "generic"

    roles = []
    if is_close_button: roles.append("close_button")
    if is_submit_button: roles.append("submit_button")
    if is_skip_button: roles.append("skip_button")
    if is_enter_button: roles.append("enter_button")
    if is_minimize_button: roles.append("minimize_button")
    if is_maximize_button: roles.append("maximize_button")
    if is_search_bar: roles.append("search_bar")
    if is_input_field: roles.append("input_field")
    if is_button: roles.append("button")
    if is_checkbox: roles.append("checkbox")
    if is_radio: roles.append("radio")
    if is_combobox: roles.append("combobox")
    if is_list_item: roles.append("list_item")
    if is_menu_item: roles.append("menu_item")
    if is_tab: roles.append("tab")
    if is_link: roles.append("link")
    if is_slider: roles.append("slider")
    if is_progress_bar: roles.append("progress_bar")
    if is_tree_item: roles.append("tree_item")
    if is_table: roles.append("table")
    if is_image: roles.append("image")
    if is_text_label: roles.append("text_label")
    if is_spinner: roles.append("spinner")
    if is_calendar: roles.append("calendar")
    if is_tooltip: roles.append("tooltip")
    if is_box: roles.append("box")
    if is_clickable: roles.append("clickable")

    return {
        "control_type": ctype,
        "control_family": control_family,
        "name": name,
        "automation_id": auto_id,
        "class_name": class_name,
        "bounding_box": bbox,
        "center": center,
        "roles": roles,
        "is_button": is_button,
        "is_search_bar": is_search_bar,
        "is_input_field": is_input_field,
        "is_close_button": is_close_button,
        "is_submit_button": is_submit_button,
        "is_skip_button": is_skip_button,
        "is_enter_button": is_enter_button,
        "is_checkbox": is_checkbox,
        "is_radio": is_radio,
        "is_combobox": is_combobox,
        "is_list_item": is_list_item,
        "is_menu_item": is_menu_item,
        "is_tab": is_tab,
        "is_link": is_link,
        "is_slider": is_slider,
        "is_progress_bar": is_progress_bar,
        "is_tree_item": is_tree_item,
        "is_table": is_table,
        "is_image": is_image,
        "is_text_label": is_text_label,
        "is_spinner": is_spinner,
        "is_calendar": is_calendar,
        "is_tooltip": is_tooltip,
        "is_box": is_box,
        "clickable": is_clickable,
    }


def uia_get_tree(window_title: str = "", depth: int = 5) -> dict:
    """Get the semantic accessibility tree with location and bounding box coordinates for each control."""
    if not auto:
        return {"success": False, "error": "uiautomation module not installed."}
    try:
        win = _get_window(window_title)
        
        global _ui_elements_cache
        _ui_elements_cache = {}
        
        def build_tree(control, current_depth=0, max_depth=5):
            if current_depth > max_depth:
                return None
            
            element_id = str(uuid.uuid4())[:8]
            _ui_elements_cache[element_id] = control
            
            info = _classify_control(control)
            node = {
                "element_id": element_id,
                "control_type": info["control_type"],
                "name": info["name"],
                "bounding_box": info["bounding_box"],
                "center": info["center"],
                "roles": info["roles"],
            }
            if info["automation_id"]:
                node["automation_id"] = info["automation_id"]
                
            try:
                node["enabled"] = control.IsEnabled
                node["offscreen"] = control.IsOffscreen
            except Exception:
                pass
                
            children = []
            for child, _ in auto.WalkControl(control, maxDepth=1):
                if child and child != control:
                    child_node = build_tree(child, current_depth + 1, max_depth)
                    if child_node:
                        # Optimization: Skip empty structural containers
                        if not child_node.get("name") and not child_node.get("automation_id") and child_node.get("control_type") in ("PaneControl", "GroupControl") and len(child_node.get("children", [])) == 1:
                            children.append(child_node["children"][0])
                        else:
                            children.append(child_node)
            
            if children:
                node["children"] = children
                
            return node
            
        tree = build_tree(win, 0, depth)
        return {"success": True, "window_title": win.Name, "tree": tree}
    except Exception as e:
        return {"success": False, "error": str(e), "traceback": traceback.format_exc()}


def uia_detect_elements(window_title: str = "", category: str = "all", max_depth: int = 5) -> dict:
    """Detect and pinpoint coordinates of buttons, search bars, type bars, and interactive elements.
    
    Category options: 'all', 'buttons', 'search_bars', 'inputs', 'close_buttons', 'submit_buttons'.
    """
    if not auto:
        return {"success": False, "error": "uiautomation module not installed."}
    try:
        win = _get_window(window_title)
        
        if is_window_accessibility_blind(win):
            return {
                "success": False,
                "error": f"Window '{win.Name or window_title}' has no accessible UIA tree (accessibility blind).",
                "reason": "accessibility_blind",
                "escalate_to_vision": True,
                "window_title": getattr(win, "Name", "") or window_title
            }

        global _ui_elements_cache
        buttons = []
        search_bars = []
        inputs = []
        close_buttons = []
        submit_buttons = []
        skip_buttons = []
        enter_buttons = []
        checkboxes = []
        radio_buttons = []
        dropdowns = []
        list_items = []
        menu_items = []
        tabs = []
        links = []
        sliders = []
        progress_bars = []
        tree_items = []
        tables = []
        images = []
        text_labels = []
        boxes = []
        clickable = []
        
        for control, _ in auto.WalkControl(win, maxDepth=max_depth):
            if not control or control == win:
                continue
            try:
                if control.IsOffscreen:
                    continue
            except Exception:
                pass
                
            info = _classify_control(control)
            if not info["name"] and not info["automation_id"] and not info["roles"]:
                continue
                
            element_id = str(uuid.uuid4())[:8]
            _ui_elements_cache[element_id] = control
            
            elem_data = {
                "element_id": element_id,
                "name": info["name"],
                "control_type": info["control_type"],
                "control_family": info.get("control_family", "generic"),
                "automation_id": info["automation_id"],
                "center": info["center"],
                "bounding_box": info["bounding_box"],
                "roles": info["roles"],
            }
            
            if info["is_close_button"]: close_buttons.append(elem_data)
            if info["is_submit_button"]: submit_buttons.append(elem_data)
            if info["is_skip_button"]: skip_buttons.append(elem_data)
            if info["is_enter_button"]: enter_buttons.append(elem_data)
            if info["is_button"]: buttons.append(elem_data)
            if info["is_search_bar"]: search_bars.append(elem_data)
            if info["is_input_field"]: inputs.append(elem_data)
            if info["is_checkbox"]: checkboxes.append(elem_data)
            if info["is_radio"]: radio_buttons.append(elem_data)
            if info["is_combobox"]: dropdowns.append(elem_data)
            if info["is_list_item"]: list_items.append(elem_data)
            if info["is_menu_item"]: menu_items.append(elem_data)
            if info["is_tab"]: tabs.append(elem_data)
            if info["is_link"]: links.append(elem_data)
            if info["is_slider"]: sliders.append(elem_data)
            if info["is_progress_bar"]: progress_bars.append(elem_data)
            if info["is_tree_item"]: tree_items.append(elem_data)
            if info["is_table"]: tables.append(elem_data)
            if info["is_image"]: images.append(elem_data)
            if info["is_text_label"]: text_labels.append(elem_data)
            if info["is_box"]: boxes.append(elem_data)
            if info["clickable"]: clickable.append(elem_data)

        all_categories = {
            "buttons": buttons,
            "search_bars": search_bars,
            "inputs": inputs,
            "close_buttons": close_buttons,
            "submit_buttons": submit_buttons,
            "skip_buttons": skip_buttons,
            "enter_buttons": enter_buttons,
            "checkboxes": checkboxes,
            "radio_buttons": radio_buttons,
            "dropdowns": dropdowns,
            "list_items": list_items,
            "menu_items": menu_items,
            "tabs": tabs,
            "links": links,
            "sliders": sliders,
            "progress_bars": progress_bars,
            "tree_items": tree_items,
            "tables": tables,
            "images": images,
            "text_labels": text_labels,
            "boxes": boxes,
            "clickable": clickable,
        }

        results = {
            "success": True,
            "window_title": win.Name,
            "counts": {k: len(v) for k, v in all_categories.items()}
        }
        
        cat_low = (category or "all").lower()
        if cat_low in all_categories:
            results[cat_low] = all_categories[cat_low]
        else:
            results.update(all_categories)

        return results
    except Exception as e:
        return {"success": False, "error": str(e), "traceback": traceback.format_exc()}


def _is_spatially_inside(child_bbox: Optional[dict], parent_bbox: Optional[dict]) -> bool:
    """Check if child_bbox is geometrically located inside parent_bbox (with 8px tolerance)."""
    if not child_bbox or not parent_bbox:
        return False
    return (
        child_bbox["left"] >= parent_bbox["left"] - 8 and
        child_bbox["top"] >= parent_bbox["top"] - 8 and
        child_bbox["right"] <= parent_bbox["right"] + 8 and
        child_bbox["bottom"] <= parent_bbox["bottom"] + 8
    )


def uia_detect_box_content(box_query: str = "", window_title: str = "", max_depth: int = 6) -> dict:
    """
    Detect an outer box/container (modal, ad box, popup, dialog, card, banner) and all
    elements nested inside it (such as Skip buttons, Enter buttons, text inputs, close buttons).
    Uses both UIA tree ancestry and 2D bounding-box spatial containment.
    """
    if not auto:
        return {"success": False, "error": "uiautomation module not installed."}
    try:
        win = _get_window(window_title)
        global _ui_elements_cache

        target_box_ctrl = None
        target_box_info = None
        box_query_lower = (box_query or "").strip().lower()

        # Step 1: Find candidate box/container
        all_controls = []
        for ctrl, _ in auto.WalkControl(win, maxDepth=max_depth):
            if not ctrl or ctrl == win:
                continue
            try:
                if ctrl.IsOffscreen:
                    continue
            except Exception:
                pass
            info = _classify_control(ctrl)
            all_controls.append((ctrl, info))

        for ctrl, info in all_controls:
            comb = f"{info['name']} {info['automation_id']} {info['class_name']}".lower()
            if box_query_lower:
                if box_query_lower in comb or (box_query_lower in ("ad", "ad box", "video ad") and any(k in comb for k in ("ad", "video", "player", "overlay", "sponsor"))):
                    target_box_ctrl = ctrl
                    target_box_info = info
                    break
            else:
                # Default: look for dialog / modal / popup / panel
                if info["control_type"] in ("DialogControl", "WindowControl") or (info["is_box"] and info["bounding_box"]):
                    target_box_ctrl = ctrl
                    target_box_info = info
                    break

        # Fallback to win itself if no smaller box specified/found
        if not target_box_ctrl:
            target_box_ctrl = win
            target_box_info = _classify_control(win)

        box_bbox = target_box_info.get("bounding_box")
        box_center = target_box_info.get("center")

        # Step 2: Find all controls inside the box (tree descendants OR spatially inside)
        inside_elements = []
        skip_buttons = []
        enter_buttons = []
        close_buttons = []
        submit_buttons = []
        buttons = []
        inputs = []

        for ctrl, info in all_controls:
            if ctrl == target_box_ctrl:
                continue

            elem_bbox = info.get("bounding_box")
            # Containment check: spatial containment or tree ancestry
            is_inside = False
            if box_bbox and elem_bbox:
                is_inside = _is_spatially_inside(elem_bbox, box_bbox)

            if not is_inside and target_box_ctrl != win:
                # Check tree parentage
                parent = getattr(ctrl, "GetParentControl", None)
                if callable(parent):
                    curr = ctrl
                    for _ in range(4):
                        curr = curr.GetParentControl() if curr else None
                        if curr == target_box_ctrl:
                            is_inside = True
                            break

            if is_inside or target_box_ctrl == win:
                element_id = str(uuid.uuid4())[:8]
                _ui_elements_cache[element_id] = ctrl
                elem_data = {
                    "element_id": element_id,
                    "name": info["name"],
                    "control_type": info["control_type"],
                    "automation_id": info["automation_id"],
                    "center": info["center"],
                    "bounding_box": info["bounding_box"],
                    "roles": info["roles"],
                }
                inside_elements.append(elem_data)
                if info["is_skip_button"]:
                    skip_buttons.append(elem_data)
                if info["is_enter_button"]:
                    enter_buttons.append(elem_data)
                if info["is_close_button"]:
                    close_buttons.append(elem_data)
                if info["is_submit_button"]:
                    submit_buttons.append(elem_data)
                if info["is_button"]:
                    buttons.append(elem_data)
                if info["is_input_field"]:
                    inputs.append(elem_data)

        return {
            "success": True,
            "window_title": win.Name,
            "box": {
                "name": target_box_info.get("name"),
                "control_type": target_box_info.get("control_type"),
                "bounding_box": box_bbox,
                "center": box_center,
            },
            "counts": {
                "all_inside": len(inside_elements),
                "skip_buttons": len(skip_buttons),
                "enter_buttons": len(enter_buttons),
                "buttons": len(buttons),
                "inputs": len(inputs),
                "close_buttons": len(close_buttons),
                "submit_buttons": len(submit_buttons),
            },
            "skip_buttons": skip_buttons,
            "enter_buttons": enter_buttons,
            "buttons": buttons,
            "inputs": inputs,
            "close_buttons": close_buttons,
            "submit_buttons": submit_buttons,
            "all_elements": inside_elements,
        }
    except Exception as e:
        return {"success": False, "error": str(e), "traceback": traceback.format_exc()}


def uia_click_inside_box(box_query: str, target: str, window_title: str = "", button: str = "left") -> dict:
    """Find a container/box and click a target button inside it (e.g., 'skip', 'enter', 'close', 'next')."""
    if not auto:
        return {"success": False, "error": "uiautomation module not installed."}

    content = uia_detect_box_content(box_query=box_query, window_title=window_title)
    if not content.get("success"):
        return content

    target_low = (target or "").strip().lower()
    chosen_elem = None

    # Role-based fast matching
    if target_low in ("skip", "skip ad", "skip intro", "skip video") and content.get("skip_buttons"):
        chosen_elem = content["skip_buttons"][0]
    elif target_low in ("enter", "next", "continue", "proceed", "go", "start") and content.get("enter_buttons"):
        chosen_elem = content["enter_buttons"][0]
    elif target_low in ("close", "exit", "cancel", "dismiss") and content.get("close_buttons"):
        chosen_elem = content["close_buttons"][0]
    elif target_low in ("submit", "save", "ok", "confirm") and content.get("submit_buttons"):
        chosen_elem = content["submit_buttons"][0]

    # Name / automation_id substring matching fallback
    if not chosen_elem:
        for elem in content.get("all_elements", []):
            name_low = (elem.get("name") or "").lower()
            id_low = (elem.get("automation_id") or "").lower()
            if target_low in name_low or target_low in id_low:
                chosen_elem = elem
                break

    if not chosen_elem:
        return {
            "success": False,
            "error": f"Target '{target}' not found inside box '{box_query}'.",
            "available_inside": [e.get("name") for e in content.get("all_elements", []) if e.get("name")]
        }

    return uia_click_element(
        window_title=window_title,
        element_id=chosen_elem.get("element_id"),
        query=chosen_elem.get("name", ""),
        button=button
    )


def uia_get_element_location(window_title: str = "", query: str = "", element_id: str = "") -> dict:
    """Get the physical screen center (x, y) and bounding box of a target UI element."""
    if not auto:
        return {"success": False, "error": "uiautomation module not installed."}
    try:
        control = None
        if element_id and element_id in _ui_elements_cache:
            control = _ui_elements_cache[element_id]
        elif query:
            find_res = uia_find(window_title, query)
            if find_res.get("success"):
                element_id = find_res["element_id"]
                control = _ui_elements_cache.get(element_id)

        if not control:
            return {"success": False, "error": f"Element '{query or element_id}' not found."}

        info = _classify_control(control)
        if not info["center"]:
            return {"success": False, "error": f"Bounding box for '{info['name']}' is unavailable or offscreen."}

        return {
            "success": True,
            "element_id": element_id,
            "name": info["name"],
            "control_type": info["control_type"],
            "center": info["center"],
            "x": info["center"]["x"],
            "y": info["center"]["y"],
            "bounding_box": info["bounding_box"],
            "roles": info["roles"]
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def uia_click_element(window_title: str = "", query: str = "", element_id: str = "", button: str = "left") -> dict:
    """Click an on-screen element directly using physical coordinates or UIA Invoke."""
    if not auto:
        return {"success": False, "error": "uiautomation module not installed."}
    try:
        control = None
        if element_id and element_id in _ui_elements_cache:
            control = _ui_elements_cache[element_id]
        elif query:
            find_res = uia_find(window_title, query)
            if find_res.get("success"):
                element_id = find_res["element_id"]
                control = _ui_elements_cache.get(element_id)

        if not control:
            return {"success": False, "error": f"Element '{query or element_id}' not found."}

        info = _classify_control(control)
        name = info["name"] or query or "element"

        # 1. Try UIA Invoke pattern first if requested left-click
        if button == "left" and hasattr(control, 'InvokePattern') and control.InvokePattern:
            try:
                control.InvokePattern.Invoke()
                return {"success": True, "message": f"Invoked UI element '{name}' via InvokePattern", "element_id": element_id}
            except Exception:
                pass

        # 2. Click physical center using MouseController
        if info["center"]:
            from app.tools.computer.mouse import MouseController
            m_ctrl = MouseController()
            cx, cy = info["center"]["x"], info["center"]["y"]
            m_ctrl.click(cx, cy, button=button)
            return {"success": True, "message": f"Clicked '{name}' at ({cx}, {cy})", "center": {"x": cx, "y": cy}, "element_id": element_id}

        # 3. Direct control click fallback
        control.Click()
        return {"success": True, "message": f"Clicked '{name}' directly", "element_id": element_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


def uia_type_into_element(window_title: str = "", query: str = "", text: str = "", element_id: str = "") -> dict:
    """Focus or click into a search bar or text box and type text."""
    if not auto:
        return {"success": False, "error": "uiautomation module not installed."}
    try:
        control = None
        if element_id and element_id in _ui_elements_cache:
            control = _ui_elements_cache[element_id]
        elif query:
            find_res = uia_find(window_title, query)
            if find_res.get("success"):
                element_id = find_res["element_id"]
                control = _ui_elements_cache.get(element_id)

        if not control:
            return {"success": False, "error": f"Target element '{query or element_id}' not found."}

        info = _classify_control(control)
        name = info["name"] or query or "input"

        # Set Value pattern if supported
        if hasattr(control, 'ValuePattern') and control.ValuePattern:
            try:
                control.ValuePattern.SetValue(text)
                return {"success": True, "message": f"Set value in '{name}'", "text": text}
            except Exception:
                pass

        # Focus / Click center and type
        if info["center"]:
            from app.tools.computer.mouse import MouseController
            from app.tools.computer.keyboard import KeyboardController
            m_ctrl = MouseController()
            kbd = KeyboardController()
            m_ctrl.click(info["center"]["x"], info["center"]["y"])
            kbd.type_text(text)
            return {"success": True, "message": f"Clicked and typed '{text}' into '{name}' at ({info['center']['x']}, {info['center']['y']})"}

        control.SetFocus()
        control.SendKeys(text)
        return {"success": True, "message": f"Typed '{text}' into '{name}'"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def uia_invoke(element_id: str) -> dict:
    control = _ui_elements_cache.get(element_id)
    if not control:
        return {"success": False, "error": f"Element {element_id} not found."}
    try:
        if hasattr(control, 'InvokePattern') and control.InvokePattern:
            control.InvokePattern.Invoke()
        else:
            control.Click()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def uia_set_value(element_id: str, value: str) -> dict:
    control = _ui_elements_cache.get(element_id)
    if not control:
        return {"success": False, "error": f"Element {element_id} not found."}
    try:
        if hasattr(control, 'ValuePattern') and control.ValuePattern:
            control.ValuePattern.SetValue(value)
        else:
            control.Click()
            control.SendKeys(value)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def uia_get_state(element_id: str) -> dict:
    control = _ui_elements_cache.get(element_id)
    if not control:
        return {"success": False, "error": f"Element {element_id} not found."}
    try:
        state = {
            "enabled": control.IsEnabled,
            "offscreen": control.IsOffscreen,
            "focused": control.HasKeyboardFocus
        }
        if hasattr(control, 'TogglePattern') and control.TogglePattern:
            state["toggled"] = control.TogglePattern.ToggleState
        if hasattr(control, 'SelectionItemPattern') and control.SelectionItemPattern:
            state["selected"] = control.SelectionItemPattern.IsSelected
        return {"success": True, "state": state}
    except Exception as e:
        return {"success": False, "error": str(e)}


def uia_get_text(element_id: str) -> dict:
    control = _ui_elements_cache.get(element_id)
    if not control:
        return {"success": False, "error": f"Element {element_id} not found."}
    try:
        text = ""
        if hasattr(control, 'ValuePattern') and control.ValuePattern:
            text = control.ValuePattern.Value
        elif hasattr(control, 'TextPattern') and control.TextPattern:
            text = control.TextPattern.DocumentRange.GetText(-1)
        else:
            text = control.Name
        return {"success": True, "text": text}
    except Exception as e:
        return {"success": False, "error": str(e)}


def uia_focus(element_id: str) -> dict:
    control = _ui_elements_cache.get(element_id)
    if not control:
        return {"success": False, "error": f"Element {element_id} not found."}
    try:
        control.SetFocus()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def uia_toggle(element_id: str) -> dict:
    control = _ui_elements_cache.get(element_id)
    if not control:
        return {"success": False, "error": f"Element {element_id} not found."}
    try:
        if hasattr(control, 'TogglePattern') and control.TogglePattern:
            control.TogglePattern.Toggle()
            return {"success": True}
        return {"success": False, "error": "Control does not support TogglePattern"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def uia_select(element_id: str) -> dict:
    control = _ui_elements_cache.get(element_id)
    if not control:
        return {"success": False, "error": f"Element {element_id} not found."}
    try:
        if hasattr(control, 'SelectionItemPattern') and control.SelectionItemPattern:
            control.SelectionItemPattern.Select()
            return {"success": True}
        return {"success": False, "error": "Control does not support SelectionItemPattern"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def uia_expand(element_id: str) -> dict:
    control = _ui_elements_cache.get(element_id)
    if not control:
        return {"success": False, "error": f"Element {element_id} not found."}
    try:
        if hasattr(control, 'ExpandCollapsePattern') and control.ExpandCollapsePattern:
            state = control.ExpandCollapsePattern.ExpandCollapseState
            if state == 0:
                control.ExpandCollapsePattern.Expand()
            else:
                control.ExpandCollapsePattern.Collapse()
            return {"success": True}
        return {"success": False, "error": "Control does not support ExpandCollapsePattern"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def uia_scroll(element_id: str, direction: str, amount: int) -> dict:
    control = _ui_elements_cache.get(element_id)
    if not control:
        return {"success": False, "error": f"Element {element_id} not found."}
    try:
        if hasattr(control, 'ScrollPattern') and control.ScrollPattern:
            h_pct, v_pct = -1, -1
            if direction == "down": v_pct = amount
            elif direction == "up": v_pct = -amount
            elif direction == "right": h_pct = amount
            elif direction == "left": h_pct = -amount
            control.ScrollPattern.SetScrollPercent(h_pct, v_pct)
            return {"success": True}
        return {"success": False, "error": "Control does not support ScrollPattern"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def uia_find(window_title: str = "", query: str = "") -> dict:
    """Find a UI element by name, automation ID, or role within a target window with location details."""
    if not auto:
        return {"success": False, "error": "uiautomation module not installed."}
    try:
        win = _get_window(window_title)

        if is_window_accessibility_blind(win):
            return {
                "success": False,
                "error": f"Window '{getattr(win, 'Name', '') or window_title}' has no accessible UIA tree (accessibility blind).",
                "reason": "accessibility_blind",
                "escalate_to_vision": True,
                "window_title": getattr(win, "Name", "") or window_title
            }

        clean_q = (query or "").strip().lower()
        
        # 1. Direct name or automation ID match
        control = win.Control(searchDepth=5, Name=query)
        if not control.Exists(0, 0):
            control = win.Control(searchDepth=5, AutomationId=query)
            
        # 2. Substring & Heuristic scan if not found directly
        if not control.Exists(0, 0):
            target_control = None
            for c, _ in auto.WalkControl(win, maxDepth=6):
                if not c or c == win:
                    continue
                c_name = (c.Name or "").lower()
                c_auto = (c.AutomationId or "").lower()
                c_type = (c.ControlTypeName or "").lower()
                
                # Role search: "search", "close", "submit"
                if clean_q == "search" and ("search" in c_name or "search" in c_auto or c_type in ("editcontrol", "comboboxcontrol")):
                    target_control = c
                    break
                elif clean_q == "close" and ("close" in c_name or "exit" in c_name or "close" in c_auto):
                    target_control = c
                    break
                elif clean_q in ("submit", "ok", "save", "enter") and (clean_q in c_name or clean_q in c_auto):
                    target_control = c
                    break
                elif clean_q in c_name or clean_q in c_auto:
                    target_control = c
                    break
            control = target_control
            
        if not control or not control.Exists(0, 0):
            return {"success": False, "error": f"Control matching '{query}' not found."}
        
        element_id = str(uuid.uuid4())[:8]
        _ui_elements_cache[element_id] = control
        info = _classify_control(control)
        
        return {
            "success": True,
            "element_id": element_id,
            "name": info["name"],
            "type": info["control_type"],
            "automation_id": info["automation_id"],
            "center": info["center"],
            "bounding_box": info["bounding_box"],
            "roles": info["roles"]
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def uia_toggle_element(window_title: str = "", query: str = "", element_id: str = "") -> dict:
    """Toggle a checkbox, radio button, or switch control by name or element ID."""
    if not auto:
        return {"success": False, "error": "uiautomation module not installed."}
    try:
        control = None
        if element_id and element_id in _ui_elements_cache:
            control = _ui_elements_cache[element_id]
        elif query:
            find_res = uia_find(window_title, query)
            if find_res.get("success"):
                element_id = find_res["element_id"]
                control = _ui_elements_cache.get(element_id)

        if not control:
            return {"success": False, "error": f"Control '{query or element_id}' not found."}

        info = _classify_control(control)
        name = info["name"] or query or "checkbox"

        # 1. Try native TogglePattern
        if hasattr(control, 'TogglePattern') and control.TogglePattern:
            try:
                control.TogglePattern.Toggle()
                new_state = getattr(control.TogglePattern, 'ToggleState', None)
                return {"success": True, "message": f"Toggled '{name}' via TogglePattern", "state": new_state, "element_id": element_id}
            except Exception:
                pass

        # 2. Try native SelectionItemPattern for radio buttons
        if hasattr(control, 'SelectionItemPattern') and control.SelectionItemPattern:
            try:
                control.SelectionItemPattern.Select()
                return {"success": True, "message": f"Selected '{name}' via SelectionItemPattern", "element_id": element_id}
            except Exception:
                pass

        # 3. Fallback: Click center coordinates
        if info["center"]:
            from app.tools.computer.mouse import MouseController
            MouseController().click(info["center"]["x"], info["center"]["y"])
            return {"success": True, "message": f"Clicked '{name}' at ({info['center']['x']}, {info['center']['y']})", "element_id": element_id}

        control.Click()
        return {"success": True, "message": f"Clicked '{name}' directly", "element_id": element_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


def uia_set_slider(window_title: str = "", query: str = "", value: float = 50.0, element_id: str = "") -> dict:
    """Set the position/value of a slider, volume bar, or range control (0 to 100)."""
    if not auto:
        return {"success": False, "error": "uiautomation module not installed."}
    try:
        control = None
        if element_id and element_id in _ui_elements_cache:
            control = _ui_elements_cache[element_id]
        elif query:
            find_res = uia_find(window_title, query)
            if find_res.get("success"):
                element_id = find_res["element_id"]
                control = _ui_elements_cache.get(element_id)

        if not control:
            return {"success": False, "error": f"Slider '{query or element_id}' not found."}

        info = _classify_control(control)
        name = info["name"] or query or "slider"
        val = max(0.0, min(100.0, float(value)))

        # 1. Try native RangeValuePattern
        if hasattr(control, 'RangeValuePattern') and control.RangeValuePattern:
            try:
                min_v = control.RangeValuePattern.Minimum
                max_v = control.RangeValuePattern.Maximum
                target_v = min_v + (max_v - min_v) * (val / 100.0)
                control.RangeValuePattern.SetValue(target_v)
                return {"success": True, "message": f"Set slider '{name}' to {target_v}", "value": target_v, "element_id": element_id}
            except Exception:
                pass

        # 2. Geometric click fallback across slider bounding box
        bbox = info.get("bounding_box")
        if bbox and bbox.get("width"):
            from app.tools.computer.mouse import MouseController
            target_x = int(bbox["left"] + (bbox["width"] * (val / 100.0)))
            target_y = int(bbox["top"] + (bbox["height"] / 2.0))
            MouseController().click(target_x, target_y)
            return {"success": True, "message": f"Moved slider '{name}' to {val}% at ({target_x}, {target_y})", "value": val, "element_id": element_id}

        return {"success": False, "error": f"Could not adjust slider '{name}'."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def uia_select_option(window_title: str = "", query: str = "", option_name: str = "", element_id: str = "") -> dict:
    """Expand a dropdown/combobox or list and select a specific option."""
    if not auto:
        return {"success": False, "error": "uiautomation module not installed."}
    try:
        control = None
        if element_id and element_id in _ui_elements_cache:
            control = _ui_elements_cache[element_id]
        elif query:
            find_res = uia_find(window_title, query)
            if find_res.get("success"):
                element_id = find_res["element_id"]
                control = _ui_elements_cache.get(element_id)

        if not control:
            return {"success": False, "error": f"Dropdown/list '{query or element_id}' not found."}

        # 1. Expand if combobox/dropdown
        if hasattr(control, 'ExpandCollapsePattern') and control.ExpandCollapsePattern:
            try:
                control.ExpandCollapsePattern.Expand()
                time.sleep(0.2)
            except Exception:
                pass

        # 2. Look for option item
        opt_low = (option_name or "").strip().lower()
        target_item = None
        for child, _ in auto.WalkControl(control, maxDepth=3):
            if child and child != control:
                c_name = (child.Name or "").strip().lower()
                if opt_low in c_name:
                    target_item = child
                    break

        if not target_item:
            # Check window-level popup lists
            win = _get_window(window_title)
            for child, _ in auto.WalkControl(win, maxDepth=4):
                if child and child.ControlTypeName in ("ListItemControl", "MenuItemControl"):
                    if opt_low in (child.Name or "").strip().lower():
                        target_item = child
                        break

        if target_item:
            if hasattr(target_item, 'SelectionItemPattern') and target_item.SelectionItemPattern:
                try:
                    target_item.SelectionItemPattern.Select()
                    return {"success": True, "message": f"Selected '{option_name}' via SelectionItemPattern"}
                except Exception:
                    pass
            # Physical click
            c_info = _classify_control(target_item)
            if c_info.get("center"):
                from app.tools.computer.mouse import MouseController
                MouseController().click(c_info["center"]["x"], c_info["center"]["y"])
                return {"success": True, "message": f"Clicked option '{option_name}' at ({c_info['center']['x']}, {c_info['center']['y']})"}

        return {"success": False, "error": f"Option '{option_name}' not found in dropdown."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def uia_get_table_data(window_title: str = "", query: str = "", max_rows: int = 25) -> dict:
    """Extract rows, columns, and headers from a Table, DataGrid, or List control as structured JSON."""
    if not auto:
        return {"success": False, "error": "uiautomation module not installed."}
    try:
        win = _get_window(window_title)
        target = None
        if query:
            find_res = uia_find(window_title, query)
            if find_res.get("success"):
                target = _ui_elements_cache.get(find_res["element_id"])

        if not target:
            # Look for foremost table / datagrid / list
            for c, _ in auto.WalkControl(win, maxDepth=4):
                if c and c.ControlTypeName in ("TableControl", "DataGridControl", "ListBoxControl"):
                    target = c
                    break

        if not target:
            return {"success": False, "error": f"Table or DataGrid matching '{query}' not found."}

        headers = []
        rows = []

        # Find header items
        for c, _ in auto.WalkControl(target, maxDepth=3):
            if c and c.ControlTypeName in ("HeaderItemControl", "HeaderControl") and c.Name:
                if c.Name not in headers:
                    headers.append(c.Name)

        # Find rows / data items
        for r_ctrl, _ in auto.WalkControl(target, maxDepth=3):
            if r_ctrl and r_ctrl.ControlTypeName in ("DataItemControl", "ListItemControl", "RowControl"):
                cells = []
                for cell, _ in auto.WalkControl(r_ctrl, maxDepth=2):
                    if cell and cell != r_ctrl and cell.Name:
                        cells.append(cell.Name)
                if not cells and r_ctrl.Name:
                    cells = [r_ctrl.Name]
                if cells:
                    rows.append(cells)
                    if len(rows) >= max_rows:
                        break

        return {
            "success": True,
            "table_name": target.Name or query or "Table",
            "control_type": target.ControlTypeName,
            "headers": headers,
            "row_count": len(rows),
            "rows": rows
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

