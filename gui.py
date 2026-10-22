"""
gui.py  –  JARVIS Top-Center Slim HUD Launcher
==============================================
Launch with:
    python gui.py
"""

import sys
import os

# Add jarvis root directory to sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.gui import run_gui

if __name__ == "__main__":
    print("Launching JARVIS Top-Center Slim HUD...")
    run_gui()
