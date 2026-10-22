import win32clipboard
from app.permissions import check_permission, PermissionLevel

def clipboard_read() -> dict:
    if not check_permission("clipboard_read", PermissionLevel.READ, {}):
        return {"success": False, "error": "Permission denied"}
        
    try:
        win32clipboard.OpenClipboard()
        try:
            data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            success = True
        except TypeError:
            data = ""
            success = True
        except Exception as e:
            data = str(e)
            success = False
        finally:
            win32clipboard.CloseClipboard()
            
        return {"success": success, "text": data}
    except Exception as e:
        return {"success": False, "error": str(e)}

def clipboard_write(text: str) -> dict:
    if not check_permission("clipboard_write", PermissionLevel.ACTION, {"text_length": len(text)}):
        return {"success": False, "error": "Permission denied"}
        
    try:
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, text)
        win32clipboard.CloseClipboard()
        return {"success": True, "message": "Text copied to clipboard"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def clipboard_clear() -> dict:
    """Empty the system clipboard."""
    return clipboard_write("")
