"""
app/gui.py  –  JARVIS Top-Center Slim HUD
==========================================
A non-intrusive, independent floating GUI that docks at the top center of the screen
like a futuristic OS Dynamic Island. Operates in the background without interfering with
system work, accepts natural language commands, executes actions asynchronously,
and displays live status with cyber visual aesthetics.
"""

import os
import sys
import time
import math
import asyncio
import threading
import tkinter as tk
from typing import Optional, List, Dict, Any

# Ensure project root is on sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.tools.uia import ensure_com_initialized


class JarvisTopCenterHUD:
    """Ultra-slim, non-intrusive Top-Center HUD floating pill widget for JARVIS OS."""

    def __init__(self):
        # Initialize COM on the UI thread
        ensure_com_initialized()

        self.root = tk.Tk()
        self.root.title("JARVIS Top-Center HUD")
        self.root.withdraw()  # Root remains hidden; we use Toplevel for frameless overlay

        # Main HUD Window
        self.hud = tk.Toplevel(self.root)
        self.hud.overrideredirect(True)      # Frameless borderless window
        self.hud.wm_attributes("-topmost", True)  # Always on top

        # Screen Geometry & Top-Center Docking
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()

        self.bar_width = 580
        self.bar_height = 46
        self.expanded_height = 120
        self.is_expanded = False
        self.is_collapsed_mini = False

        self.pos_x = (self.screen_width - self.bar_width) // 2
        self.pos_y = 10  # 10px below top bezel

        self.hud.geometry(f"{self.bar_width}x{self.bar_height}+{self.pos_x}+{self.pos_y}")
        self.hud.configure(bg="#0b0f19")

        # Color Palette (High-Tech Cyber Glass)
        self.BG_DARK = "#0d1117"
        self.BG_CARD = "#161b22"
        self.BG_INPUT = "#1c2128"
        self.CYAN = "#00e5ff"
        self.PURPLE = "#7c4dff"
        self.GREEN = "#00e676"
        self.ORANGE = "#ff9100"
        self.RED = "#ff1744"
        self.TEXT_MUTED = "#8b949e"
        self.TEXT_WHITE = "#f0f6fc"

        # State Variables
        self.state = "idle"  # idle, listening, executing, error, success
        self.anim_step = 0
        self.is_listening = False
        self._hide_timer = None
        self._drag_start_x = 0
        self._drag_start_y = 0

        # Background Core & Event Loop
        self.core = None
        self.mcp_client = None
        self.bg_loop = None
        self._init_backend_thread()

        # Build UI Components
        self._build_ui()

        # Start Pulse Animation Loop
        self._animate()

        # Global hotkey listener (Ctrl+Space to summon/focus)
        self._init_global_hotkey()

    # -----------------------------------------------------------------------
    # UI Layout & Aesthetics
    # -----------------------------------------------------------------------
    def _build_ui(self):
        # Outer Glowing Container Border
        self.outer_frame = tk.Frame(
            self.hud,
            bg=self.CYAN,
            bd=1,
            relief=tk.FLAT
        )
        self.outer_frame.pack(fill=tk.BOTH, expand=True)

        self.main_frame = tk.Frame(self.outer_frame, bg=self.BG_DARK)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # Top Bar Row
        self.top_row = tk.Frame(self.main_frame, bg=self.BG_DARK, height=44)
        self.top_row.pack(fill=tk.X, padx=8, pady=4)
        self.top_row.pack_propagate(False)

        # Draggable Grab Handle / Status Orb
        self.orb_canvas = tk.Canvas(
            self.top_row,
            width=30,
            height=30,
            bg=self.BG_DARK,
            highlightthickness=0,
            cursor="hand2"
        )
        self.orb_canvas.pack(side=tk.LEFT, padx=(2, 6))
        self.orb_canvas.bind("<Button-1>", self._start_drag)
        self.orb_canvas.bind("<B1-Motion>", self._on_drag)

        # Logo / Badge
        self.lbl_logo = tk.Label(
            self.top_row,
            text="JARVIS",
            font=("Segoe UI", 9, "bold"),
            fg=self.CYAN,
            bg=self.BG_DARK,
            cursor="hand2"
        )
        self.lbl_logo.pack(side=tk.LEFT, padx=(0, 8))
        self.lbl_logo.bind("<Button-1>", self._start_drag)
        self.lbl_logo.bind("<B1-Motion>", self._on_drag)

        # Input Entry Field (Slim Pill Embedded)
        self.input_frame = tk.Frame(
            self.top_row,
            bg=self.BG_INPUT,
            highlightbackground="#30363d",
            highlightthickness=1
        )
        self.input_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))

        self.entry_var = tk.StringVar()
        self.entry = tk.Entry(
            self.input_frame,
            textvariable=self.entry_var,
            font=("Segoe UI", 10),
            bg=self.BG_INPUT,
            fg=self.TEXT_WHITE,
            insertbackground=self.CYAN,
            bd=0
        )
        self.entry.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        self.entry.insert(0, "Type a command or ask JARVIS... (Enter)")
        self.entry.bind("<FocusIn>", self._on_entry_focus_in)
        self.entry.bind("<FocusOut>", self._on_entry_focus_out)
        self.entry.bind("<Return>", self._submit_text_command)
        self.entry.bind("<Escape>", lambda e: self._collapse_to_slim())

        # Action Buttons (Mic, Quick Actions, Collapse, Close)
        # 1. Voice Button
        self.btn_mic = tk.Label(
            self.top_row,
            text="🎙️",
            font=("Segoe UI", 11),
            fg=self.TEXT_MUTED,
            bg=self.BG_DARK,
            cursor="hand2"
        )
        self.btn_mic.pack(side=tk.LEFT, padx=3)
        self.btn_mic.bind("<Button-1>", lambda e: self._toggle_voice())

        # 2. Quick Media Play Button
        self.btn_play = tk.Label(
            self.top_row,
            text="🎵",
            font=("Segoe UI", 11),
            fg=self.TEXT_MUTED,
            bg=self.BG_DARK,
            cursor="hand2"
        )
        self.btn_play.pack(side=tk.LEFT, padx=3)
        self.btn_play.bind("<Button-1>", lambda e: self._quick_template("play "))

        # 3. Quick Search Button
        self.btn_search = tk.Label(
            self.top_row,
            text="🔍",
            font=("Segoe UI", 11),
            fg=self.TEXT_MUTED,
            bg=self.BG_DARK,
            cursor="hand2"
        )
        self.btn_search.pack(side=tk.LEFT, padx=3)
        self.btn_search.bind("<Button-1>", lambda e: self._quick_template("search "))

        # 4. Collapse Toggle
        self.btn_toggle = tk.Label(
            self.top_row,
            text="▾",
            font=("Segoe UI", 11),
            fg=self.TEXT_MUTED,
            bg=self.BG_DARK,
            cursor="hand2"
        )
        self.btn_toggle.pack(side=tk.LEFT, padx=3)
        self.btn_toggle.bind("<Button-1>", lambda e: self._toggle_drawer())

        # 5. Close HUD Button
        self.btn_close = tk.Label(
            self.top_row,
            text="✕",
            font=("Segoe UI", 9),
            fg=self.TEXT_MUTED,
            bg=self.BG_DARK,
            cursor="hand2"
        )
        self.btn_close.pack(side=tk.LEFT, padx=(3, 2))
        self.btn_close.bind("<Button-1>", lambda e: self._on_close())

        # --- Expandable Response Drawer (Below Top Bar) ---
        self.drawer_frame = tk.Frame(self.main_frame, bg=self.BG_CARD)
        # Hidden by default

        self.lbl_status = tk.Label(
            self.drawer_frame,
            text="⚡ Ready",
            font=("Consolas", 9),
            fg=self.CYAN,
            bg=self.BG_CARD,
            anchor="w"
        )
        self.lbl_status.pack(fill=tk.X, padx=12, pady=(4, 2))

        self.lbl_result = tk.Label(
            self.drawer_frame,
            text="",
            font=("Segoe UI", 9),
            fg=self.TEXT_WHITE,
            bg=self.BG_CARD,
            anchor="w",
            justify=tk.LEFT,
            wraplength=self.bar_width - 30
        )
        self.lbl_result.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 6))

    # -----------------------------------------------------------------------
    # Draggable Window Mechanics
    # -----------------------------------------------------------------------
    def _start_drag(self, event):
        self._drag_start_x = event.x_root - self.hud.winfo_x()
        self._drag_start_y = event.y_root - self.hud.winfo_y()

    def _on_drag(self, event):
        new_x = event.x_root - self._drag_start_x
        new_y = event.y_root - self._drag_start_y
        self.pos_x = max(0, min(self.screen_width - 100, new_x))
        self.pos_y = max(0, min(self.screen_height - 50, new_y))
        curr_h = self.expanded_height if self.is_expanded else self.bar_height
        self.hud.geometry(f"{self.bar_width}x{curr_h}+{self.pos_x}+{self.pos_y}")

    # -----------------------------------------------------------------------
    # Animation: Arc Reactor Glowing Pulse
    # -----------------------------------------------------------------------
    def _animate(self):
        try:
            self.orb_canvas.delete("all")
            cx, cy = 15, 15

            # Dynamic Arc Color based on state
            if self.state == "listening":
                color = self.ORANGE
                # Expanding soundwave rings
                phase = (self.anim_step * 0.2) % 3
                r = 6 + (phase * 4)
                self.orb_canvas.create_oval(cx - r, cy - r, cx + r, cy + r, outline=self.ORANGE, width=1)
                self.outer_frame.configure(bg=self.ORANGE)
            elif self.state == "executing":
                color = self.GREEN
                # Rotating spinner
                angle = (self.anim_step * 25) % 360
                self.orb_canvas.create_arc(
                    cx - 9, cy - 9, cx + 9, cy + 9,
                    start=angle, extent=120,
                    style=tk.ARC, outline=self.GREEN, width=2
                )
                self.outer_frame.configure(bg=self.GREEN)
            elif self.state == "error":
                color = self.RED
                self.outer_frame.configure(bg=self.RED)
            else:
                color = self.CYAN
                # Gentle cyan breathing pulse
                pulse = 1.0 + 0.15 * math.sin(self.anim_step * 0.1)
                r = int(5 * pulse)
                self.orb_canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=self.CYAN, outline="")
                self.outer_frame.configure(bg=self.CYAN)

            # Central Core
            self.orb_canvas.create_oval(cx - 3, cy - 3, cx + 3, cy + 3, fill=color, outline="")

            self.anim_step += 1
            self.hud.after(45, self._animate)
        except Exception:
            pass

    # -----------------------------------------------------------------------
    # Input & Command Handling
    # -----------------------------------------------------------------------
    def _on_entry_focus_in(self, event):
        if self.entry.get().startswith("Type a command"):
            self.entry.delete(0, tk.END)
            self.entry.configure(fg=self.TEXT_WHITE)

    def _on_entry_focus_out(self, event):
        if not self.entry.get().strip():
            self.entry.insert(0, "Type a command or ask JARVIS... (Enter)")
            self.entry.configure(fg=self.TEXT_MUTED)

    def _quick_template(self, prefix: str):
        self.entry.delete(0, tk.END)
        self.entry.insert(0, prefix)
        self.entry.configure(fg=self.TEXT_WHITE)
        self.entry.focus_set()
        self.entry.icursor(tk.END)

    def _submit_text_command(self, event=None):
        cmd = self.entry.get().strip()
        if not cmd or cmd.startswith("Type a command"):
            return

        self.entry.delete(0, tk.END)
        self.set_state("executing")
        self.show_feedback(f"⚡ Routing: '{cmd}'", "Executing via JARVIS pipeline...")

        # Run command in background thread with COM initialized
        threading.Thread(target=self._run_command_async, args=(cmd,), daemon=True).start()

    def _run_command_async(self, command_text: str):
        ensure_com_initialized()
        try:
            if not self.core or not self.bg_loop:
                self.root.after(0, lambda: self.show_feedback("⚠ System Error", "JARVIS Core not yet initialized."))
                self.set_state("error")
                return

            future = asyncio.run_coroutine_threadsafe(
                self.core.process_request(command_text, []),
                self.bg_loop
            )
            history, response = future.result(timeout=45)

            # Update UI on main thread
            self.root.after(0, lambda: self._handle_result(command_text, response))
        except Exception as exc:
            self.root.after(0, lambda: self._handle_error(str(exc)))

    def _handle_result(self, cmd: str, response: str):
        self.set_state("idle")
        resp_clean = str(response).strip()
        lines = resp_clean.splitlines()
        first_line = lines[0] if lines else "Done."
        full_text = "\n".join(lines[:4])

        self.show_feedback(f"✔ Completed", f"{cmd}\n{full_text}")

    def _handle_error(self, err_msg: str):
        self.set_state("error")
        self.show_feedback("✖ Command Failed", err_msg)

    # -----------------------------------------------------------------------
    # Feedback Drawer Expansion & Auto-Collapse
    # -----------------------------------------------------------------------
    def show_feedback(self, status: str, message: str):
        self.lbl_status.configure(text=status)
        self.lbl_result.configure(text=message)

        if not self.is_expanded:
            self.drawer_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))
            self.hud.geometry(f"{self.bar_width}x{self.expanded_height}+{self.pos_x}+{self.pos_y}")
            self.btn_toggle.configure(text="▴")
            self.is_expanded = True

        # Auto-collapse back to slim bar after 6 seconds
        if self._hide_timer:
            self.hud.after_cancel(self._hide_timer)
        self._hide_timer = self.hud.after(6000, self._collapse_to_slim)

    def _collapse_to_slim(self):
        if self.is_expanded:
            self.drawer_frame.pack_forget()
            self.hud.geometry(f"{self.bar_width}x{self.bar_height}+{self.pos_x}+{self.pos_y}")
            self.btn_toggle.configure(text="▾")
            self.is_expanded = False

    def _toggle_drawer(self):
        if self.is_expanded:
            self._collapse_to_slim()
        else:
            self.drawer_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))
            self.hud.geometry(f"{self.bar_width}x{self.expanded_height}+{self.pos_x}+{self.pos_y}")
            self.btn_toggle.configure(text="▴")
            self.is_expanded = True

    def set_state(self, state: str):
        self.state = state

    # -----------------------------------------------------------------------
    # Voice Control Support
    # -----------------------------------------------------------------------
    def _toggle_voice(self):
        if self.is_listening:
            self.is_listening = False
            self.set_state("idle")
            self.btn_mic.configure(fg=self.TEXT_MUTED)
            self.show_feedback("🎙️ Voice Standby", "Voice listening stopped.")
        else:
            self.is_listening = True
            self.set_state("listening")
            self.btn_mic.configure(fg=self.ORANGE)
            self.show_feedback("🎙️ Listening...", "Speak your command now...")
            threading.Thread(target=self._voice_record_worker, daemon=True).start()

    def _voice_record_worker(self):
        ensure_com_initialized()
        try:
            from app.voice.voice import record_audio, transcribe_audio
            audio_path = record_audio(timeout=6.0)
            if not audio_path or not self.is_listening:
                self.root.after(0, lambda: self._end_voice())
                return

            self.root.after(0, lambda: self.show_feedback("🧠 Transcribing...", "Converting voice audio..."))
            text = transcribe_audio(audio_path)
            if os.path.exists(audio_path):
                try: os.remove(audio_path)
                except Exception: pass

            if text and text.strip():
                clean_text = text.strip()
                self.root.after(0, lambda: self.entry.delete(0, tk.END))
                self.root.after(0, lambda: self.entry.insert(0, clean_text))
                self.root.after(0, lambda: self._submit_text_command())
            self.root.after(0, lambda: self._end_voice())
        except Exception as e:
            self.root.after(0, lambda: self.show_feedback("🎙️ Voice Error", str(e)))
            self.root.after(0, lambda: self._end_voice())

    def _end_voice(self):
        self.is_listening = False
        self.btn_mic.configure(fg=self.TEXT_MUTED)
        if self.state == "listening":
            self.set_state("idle")

    # -----------------------------------------------------------------------
    # Global Hotkey (Ctrl+Space to Summon / Focus)
    # -----------------------------------------------------------------------
    def _init_global_hotkey(self):
        def _hotkey_thread():
            try:
                from pynput import keyboard
                with keyboard.GlobalHotKeys({'<ctrl>+<space>': self._on_hotkey_pressed}) as h:
                    h.join()
            except Exception:
                pass

        threading.Thread(target=_hotkey_thread, daemon=True).start()

    def _on_hotkey_pressed(self):
        self.root.after(0, self._focus_hud)

    def _focus_hud(self):
        self.hud.deiconify()
        self.hud.lift()
        self.entry.focus_set()
        if self.entry.get().startswith("Type a command"):
            self.entry.delete(0, tk.END)

    def _on_close(self):
        try:
            self.hud.destroy()
            self.root.destroy()
        except Exception:
            pass
        os._exit(0)

    # -----------------------------------------------------------------------
    # Background Backend Initialization
    # -----------------------------------------------------------------------
    def _init_backend_thread(self):
        def _start_loop():
            ensure_com_initialized()
            self.bg_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.bg_loop)

            # Initialize MCP and JarvisCore
            from app.mcp_client import FileSystemMCPClient
            from app.core import JarvisCore
            try:
                self.mcp_client = FileSystemMCPClient("C:\\")
                self.bg_loop.run_until_complete(self.mcp_client.connect())
            except Exception:
                self.mcp_client = None

            self.core = JarvisCore(self.mcp_client)
            self.bg_loop.run_forever()

        t = threading.Thread(target=_start_loop, daemon=True)
        t.start()

    def run(self):
        """Start the GUI event loop."""
        self.hud.deiconify()
        self.hud.lift()
        self.root.mainloop()


def run_gui():
    """Entry point to launch the top-center HUD."""
    hud = JarvisTopCenterHUD()
    hud.run()


if __name__ == "__main__":
    run_gui()
