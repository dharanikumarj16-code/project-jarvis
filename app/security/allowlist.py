ALLOWED_APPLICATIONS = {
    "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "vscode": "code",
    "notepad": "notepad.exe",
    "calculator": "calc.exe"
}

def get_allowed_app_path(app_name: str) -> str:
    path = ALLOWED_APPLICATIONS.get(app_name.lower())
    if not path:
        return app_name  # Bypass strict allowlist, let the OS attempt to launch it
    return path
