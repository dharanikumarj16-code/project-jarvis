import tkinter as tk
import threading
import time
import math

class JarvisGUI:
    def __init__(self, on_command=None):
        self.root = tk.Tk()
        self.root.withdraw()  # Hide the root window
        self.on_command = on_command
        
        # --- 3.1 Always-On HUD (Voice Controller Icon) ---
        self.hud = tk.Toplevel(self.root)
        self.hud.overrideredirect(True) # Frameless
        self.hud.wm_attributes("-topmost", True) # Always on top
        
        # Windows-specific transparency (Black becomes transparent)
        try:
            self.hud.wm_attributes("-transparentcolor", "black")
        except:
            pass 
            
        # Position: Top Right Corner
        screen_width = self.root.winfo_screenwidth()
        self.hud.geometry(f"60x60+{screen_width-80}+20")
        self.hud.configure(bg="black")
        
        self.canvas = tk.Canvas(self.hud, width=60, height=60, bg="black", highlightthickness=0)
        self.canvas.pack()
        
        # Interaction State
        self._press_start = 0
        self.listening_enabled = True
        
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        # Animation State
        self.state = "idle"
        self.anim_step = 0
        self._animate()
        
        # --- 3.2 Command Bar (Universal) ---
        self.bar = tk.Toplevel(self.root)
        self.bar.overrideredirect(True)
        self.bar.wm_attributes("-topmost", True)
        
        # Centered Command Bar
        bar_width = 600
        bar_x = (screen_width - bar_width) // 2
        self.bar.geometry(f"{bar_width}x60+{bar_x}+100")
        self.bar.withdraw() # Hidden by default
        self.bar.configure(bg="#1e1e1e")
        
        # Input Field
        self.entry = tk.Entry(self.bar, font=("Segoe UI", 14), bg="#333333", fg="white", insertbackground="white", bd=0)
        self.entry.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.entry.bind("<Return>", self.submit_command)
        self.entry.bind("<Escape>", lambda e: self.bar.withdraw())
        
        # State Colors
        self.state_colors = {
            "idle": "#00FFFF",      # Cyan (Waiting)
            "listening": "#FFaa00", # Orange (Mic Active)
            "executing": "#00FF00", # Green (Processing)
            "error": "#FF0000",     # Red (Error)
            "ai_work": "#FF00FF",   # Magenta (AI Work Mode)
            "chat": "#FFFF00"       # Yellow (Chat Mode)
        }

        # --- 3.3 Output Overlay (Top of Screen) ---
        self.output_overlay = tk.Toplevel(self.root)
        self.output_overlay.overrideredirect(True)
        self.output_overlay.wm_attributes("-topmost", True)
        self.output_overlay.withdraw() # Hidden by default
        
        # Try to make the window background transparent (Windows specific)
        try:
            self.output_overlay.wm_attributes("-transparentcolor", "black")
            self.output_overlay.configure(bg="black")
        except:
            self.output_overlay.configure(bg="#1e1e1e")

        # Content Frame (Dark Grey card look)
        self.msg_frame = tk.Frame(self.output_overlay, bg="#1e1e1e", highlightbackground="#00FFFF", highlightthickness=1)
        self.msg_frame.pack(fill=tk.BOTH, expand=True)
        
        # Labels for User and Jarvis
        self.lbl_user = tk.Label(self.msg_frame, text="", font=("Segoe UI", 10), fg="#aaaaaa", bg="#1e1e1e", anchor="w")
        self.lbl_user.pack(fill=tk.X, padx=15, pady=(10, 2))
        
        self.lbl_jarvis = tk.Label(self.msg_frame, text="", font=("Segoe UI", 12), fg="white", bg="#1e1e1e", anchor="w", justify=tk.LEFT, wraplength=560)
        self.lbl_jarvis.pack(fill=tk.X, padx=15, pady=(0, 15))

    def _on_press(self, event):
        self._press_start = time.time()

    def _on_release(self, event):
        duration = time.time() - self._press_start
        if duration < 0.5:
            # Tap: Toggle Listening / Mute
            self.listening_enabled = not self.listening_enabled
            self.set_state("error" if not self.listening_enabled else "idle")
            # Visual Haptic: Flash background briefly
            self.canvas.configure(bg="#333333")
            self.root.after(100, lambda: self.canvas.configure(bg="black"))
        else:
            # Long Press: Open Command Bar / Settings
            self.toggle_bar()

    def _draw_mic_icon(self, color="white", scale=1.0, muted=False):
        """Helper to draw vector microphone"""
        cx, cy = 30, 30
        
        # Mic body (Capsule)
        self.canvas.create_rectangle(cx-6, cy-10, cx+6, cy+5, fill=color, outline=color, tags="mic")
        self.canvas.create_oval(cx-6, cy-10, cx+6, cy-4, fill=color, outline=color, tags="mic") # Top cap
        self.canvas.create_oval(cx-6, cy+2, cx+6, cy+8, fill=color, outline=color, tags="mic")  # Bottom cap
        
        # Stand (U-shape)
        self.canvas.create_arc(cx-12, cy-5, cx+12, cy+15, start=180, extent=180, style=tk.ARC, outline=color, width=2, tags="mic")
        # Stem & Base
        self.canvas.create_line(cx, cy+15, cx, cy+22, fill=color, width=2, tags="mic")
        self.canvas.create_line(cx-8, cy+22, cx+8, cy+22, fill=color, width=2, tags="mic")

        if muted:
            self.canvas.create_line(cx-10, cy-10, cx+10, cy+20, fill="#FF0000", width=3, tags="mic")

    def _animate(self):
        """Main Animation Loop"""
        self.canvas.delete("all")
        cx, cy = 30, 30

        # 1. Error / Muted State
        if self.state == "error" or not self.listening_enabled:
            self._draw_mic_icon(color="#555555", muted=True)

        # 2. Processing State (Spinner)
        elif self.state == "executing":
            # Three bouncing dots
            for i in range(3):
                offset = (self.anim_step + i * 4) % 20
                y_bounce = cy + math.sin(offset * 0.5) * 5
                x_pos = cx - 12 + (i * 12)
                self.canvas.create_oval(x_pos-3, y_bounce-3, x_pos+3, y_bounce+3, fill="#00FF00", outline="")

        # 3. Active Listening / AI Work / Chat (Pulsing)
        elif self.state in ["listening", "ai_work", "chat"]:
            color = self.state_colors.get(self.state, "#00FFFF")
            # Pulsing Ripples (Multiple circles expanding)
            for i in range(3):
                # Create a staggered expansion effect
                phase = (self.anim_step * 0.15 + i * 2) % 4
                radius = 10 + (phase * 5)
                
                if radius < 28:
                    # Thinner line as it expands to simulate fading
                    width = max(1, 3 - int(phase))
                    self.canvas.create_oval(cx-radius, cy-radius, cx+radius, cy+radius, 
                                          outline=color, width=width)
            self._draw_mic_icon(color=color)

        # 4. Idle State
        else:
            self._draw_mic_icon(color="white")

        self.anim_step += 1
        self.root.after(50, self._animate)

    def set_state(self, state):
        """Update HUD color based on state"""
        # Only update if listening is enabled or if it's an error
        if self.listening_enabled or state == "error":
            self.state = state

    def toggle_bar(self, event=None):
        """Show/Hide Command Bar"""
        if self.bar.state() == "withdrawn":
            self.bar.deiconify()
            self.entry.focus_set()
        else:
            self.bar.withdraw()

    def submit_command(self, event):
        """Handle text submission"""
        text = self.entry.get().strip()
        if text:
            self.bar.withdraw()
            self.entry.delete(0, tk.END)
            if self.on_command:
                # Run in separate thread to avoid freezing UI
                threading.Thread(target=self.on_command, args=(text,)).start()

    def show_message(self, user_text, jarvis_text):
        """Show conversation overlay at top of screen"""
        def _update():
            # Reset packing to handle optional user text
            self.lbl_user.pack_forget()
            self.lbl_jarvis.pack_forget()

            if user_text:
                # Conversation Mode
                self.lbl_user.config(text=f"You: {user_text}")
                self.lbl_user.pack(fill=tk.X, padx=15, pady=(10, 2))
                self.lbl_jarvis.pack(fill=tk.X, padx=15, pady=(0, 15))
            else:
                # System Notification Mode (No "You")
                self.lbl_jarvis.pack(fill=tk.X, padx=15, pady=15)

            self.lbl_jarvis.config(text=f"{jarvis_text}")
            
            # Calculate position (Top Center)
            screen_width = self.root.winfo_screenwidth()
            width = 600
            x = (screen_width - width) // 2
            
            # Update geometry based on content height
            self.msg_frame.update_idletasks() 
            height = self.msg_frame.winfo_reqheight()
            self.output_overlay.geometry(f"{width}x{height}+{x}+80")
            
            self.output_overlay.deiconify()
            
            # Auto-hide after 6 seconds
            if hasattr(self, '_hide_timer'):
                self.root.after_cancel(self._hide_timer)
            self._hide_timer = self.root.after(6000, self.output_overlay.withdraw)
            
        self.root.after(0, _update)

    def start(self):
        """Start the GUI loop"""
        self.root.mainloop()
