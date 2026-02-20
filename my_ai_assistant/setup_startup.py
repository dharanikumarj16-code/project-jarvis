import sys
import os
import winreg

def manage_startup(enable=True):
    """
    Adds or removes Jarvis from Windows Startup (Registry).
    Uses pythonw.exe to run in the background (no console).
    """
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    app_name = "JarvisAI"
    
    try:
        # Open Registry Key
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
        
        if enable:
            # Determine paths
            current_dir = os.path.dirname(os.path.abspath(__file__))
            script_path = os.path.join(current_dir, "main.py")
            
            # Use pythonw.exe for background execution (no console window)
            python_exe = sys.executable.replace("python.exe", "pythonw.exe")
            if not os.path.exists(python_exe):
                print("⚠️ pythonw.exe not found. Using python.exe (Console will be visible).")
                python_exe = sys.executable
            
            # Command: "path\to\pythonw.exe" "path\to\main.py"
            command = f'"{python_exe}" "{script_path}"'
            
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, command)
            print(f"✅ Jarvis Startup ENABLED.")
            print(f"   Target: {command}")
            print("   Jarvis will start automatically in the background on next login.")
            
        else:
            try:
                winreg.DeleteValue(key, app_name)
                print(f"✅ Jarvis Startup DISABLED.")
            except FileNotFoundError:
                print("ℹ️ Jarvis is not currently set to start on boot.")
        
        winreg.CloseKey(key)
        
    except Exception as e:
        print(f"❌ Error managing startup: {e}")

if __name__ == "__main__":
    print("🤖 Jarvis System Service Manager")
    print("--------------------------------")
    print("1. Enable Start on Boot (Background/Silent)")
    print("2. Disable Start on Boot")
    
    choice = input("\nSelect option (1/2): ").strip()
    
    if choice == "1":
        manage_startup(True)
    elif choice == "2":
        manage_startup(False)
    else:
        print("Invalid choice.")
