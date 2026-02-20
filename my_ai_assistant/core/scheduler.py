import threading
import time
import datetime
from output.speech import speak
try:
    import pyautogui
except ImportError:
    pyautogui = None

class JarvisScheduler:
    def __init__(self):
        self.alarms = []
        self.silent_schedules = []
        self.running = False
        self.lock = threading.Lock()

    def start(self):
        if self.running: return
        self.running = True
        threading.Thread(target=self._run_loop, daemon=True).start()

    def add_alarm(self, dt, message="Alarm"):
        with self.lock:
            self.alarms.append({"time": dt, "message": message})
        return f"Alarm set for {dt.strftime('%I:%M %p, %B %d')}"

    def set_silent_mode(self, start_dt, end_dt, repeat=False):
        with self.lock:
            sid = len(self.silent_schedules) + 1
            self.silent_schedules.append({
                "id": sid,
                "start": start_dt,
                "end": end_dt,
                "repeat": repeat,
                "active": False,
                "completed": False
            })
        mode = "Daily" if repeat else "One-time"
        return f"Silent mode scheduled: {start_dt.strftime('%I:%M %p')} - {end_dt.strftime('%I:%M %p')} ({mode})"

    def _toggle_mute(self):
        if pyautogui:
            pyautogui.press('volumemute')
        else:
            print("[System] Toggling Mute (pyautogui missing)")

    def _run_loop(self):
        while self.running:
            now = datetime.datetime.now()
            with self.lock:
                # 1. Check Alarms
                remaining = []
                for alarm in self.alarms:
                    if now >= alarm["time"]:
                        print(f"\n⏰ ALARM: {alarm['message']}")
                        speak(f"Alarm ringing! {alarm['message']}")
                        print('\a') # System beep
                    else:
                        remaining.append(alarm)
                self.alarms = remaining

                # 2. Check Silent Mode
                for s in self.silent_schedules:
                    if s.get("completed"): continue

                    # Determine effective start/end for today/now
                    if s["repeat"]:
                        # Create timestamps for today
                        start_t = now.replace(hour=s["start"].hour, minute=s["start"].minute, second=0, microsecond=0)
                        end_t = now.replace(hour=s["end"].hour, minute=s["end"].minute, second=0, microsecond=0)
                        
                        # Handle overnight (e.g. 10pm to 7am)
                        if end_t < start_t:
                            if now < end_t: start_t -= datetime.timedelta(days=1) # Started yesterday
                            else: end_t += datetime.timedelta(days=1) # Ends tomorrow

                        should_be_active = start_t <= now < end_t
                        
                        if should_be_active and not s["active"]:
                            print(f"\n🔕 Silent Mode ON (Schedule #{s['id']})")
                            self._toggle_mute()
                            s["active"] = True
                        elif not should_be_active and s["active"]:
                            print(f"\n🔔 Silent Mode OFF (Schedule #{s['id']})")
                            self._toggle_mute()
                            s["active"] = False
                    else:
                        # One time
                        if not s["active"] and now >= s["start"] and now < s["end"]:
                            print(f"\n🔕 Silent Mode ON")
                            self._toggle_mute()
                            s["active"] = True
                        elif s["active"] and now >= s["end"]:
                            print(f"\n🔔 Silent Mode OFF")
                            self._toggle_mute()
                            s["active"] = False
                            s["completed"] = True

                # Cleanup completed one-time schedules
                self.silent_schedules = [s for s in self.silent_schedules if not s.get("completed", False)]

            time.sleep(2)

scheduler = JarvisScheduler()
