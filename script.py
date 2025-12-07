import keyboard
import subprocess
import webbrowser
import time
import threading
import psutil
import sys
import os
from datetime import datetime
import json
import tkinter as tk

# =========================
# ✅ LOAD CONFIG (SAFE)
# =========================
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
LOG_FILE = os.path.join(BASE_DIR, "log.txt")

if not os.path.exists(CONFIG_PATH):
    print("❌ config.json not found:", CONFIG_PATH)
    input("Press Enter to exit...")
    sys.exit(1)

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    cf = json.load(f)

BROWSER_URL     = cf.get("browser", "https://www.google.com")
ANTIGRAVITY     = cf.get("antigravity", "")
POSTMAN_PATH   = cf.get("postman", "")
SLACK_PATH     = cf.get("slack", "")
MONGODB_PATH   = cf.get("mongodb", "")
RUN_TIME       = cf.get("run_time_minute", 20) * 60
DEBOUNCE_SECOND = cf.get("debounce_second", 2)


# =========================
# ✅ LOG SYSTEM
# =========================
def write_log(msg):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{now} - {msg}\n")

# =========================
# ✅ SYSTEM STATE
# =========================
START_TIME = time.time()
system_active = True
system_paused = False
already_opened = False
shutdown_requested = False
last_press_time = 0
status_window = None

# =========================
# ✅ UTILS
# =========================
def is_process_running(process_name):
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] and process_name.lower() in proc.info['name'].lower():
                return True
        except:
            pass
    return False

def safe_open_app(path, process_name):
    if not path or not os.path.exists(path):
        write_log(f"{process_name} path invalid")
        return

    if not is_process_running(process_name):
        subprocess.Popen([path], shell=True)
        write_log(f"{process_name} opened")
    else:
        write_log(f"{process_name} already running")

# =========================
# ✅ MAIN OPEN FUNCTION
# =========================
def dev_mode():
    global already_opened, last_press_time

    now = time.time()
    if now - last_press_time < DEBOUNCE_SECOND:
        return
    last_press_time = now

    if system_paused:
        write_log("Blocked: system paused")
        return

    if not system_active or already_opened:
        write_log("Blocked: already executed")
        return

    already_opened = True
    write_log("OPEN ALL triggered")

    try:
        webbrowser.open(BROWSER_URL)

        safe_open_app(ANTIGRAVITY, "antigravity")
        safe_open_app(POSTMAN_PATH, "postman")
        safe_open_app(SLACK_PATH, "slack")
        safe_open_app(MONGODB_PATH, "mongodb")

        write_log("All applications handled")

    except Exception as e:
        write_log("Open error: " + str(e))


def homr_mode():
    global already_opened, last_press_time

    now = time.time()
    if now - last_press_time < DEBOUNCE_SECOND:
        return
    last_press_time = now

    if system_paused:
        write_log("Blocked: system paused")
        return

    if not system_active or already_opened:
        write_log("Blocked: already executed")
        return

    already_opened = True
    write_log("OPEN ALL triggered")

    try:
        webbrowser.open(BROWSER_URL)
        write_log("Open Browser handled")

    except Exception as e:
        write_log("Open error: " + str(e))

# =========================
# ✅ SYSTEM CONTROL
# =========================
def toggle_paused():
    global system_paused
    system_paused = not system_paused
    write_log(f"Paused: {system_paused}")
    show_status_pop()

def start_system():
    global already_opened, system_active
    already_opened = False
    system_active = True
    write_log("System reset")
    show_status_pop()

# =========================
# ✅ SOFT → TERMINATE → KILL
# =========================
def soft_shutdown():
    global shutdown_requested

    if shutdown_requested:
        return

    shutdown_requested = True
    write_log("Shutdown requested")

    def shutdown_sequence():
        try:
            keyboard.unhook_all()
            time.sleep(1)

            p = psutil.Process(os.getpid())

            if p.is_running():
                write_log("Trying terminate()")
                p.terminate()

            time.sleep(3)

            if p.is_running():
                write_log("Fallback kill()")
                p.kill()

        except Exception as e:
            write_log("Shutdown error: " + str(e))

    threading.Thread(target=shutdown_sequence, daemon=True).start()

def stop_system():
    write_log("Stop triggered by hotkey")
    soft_shutdown()

# =========================
# ✅ STATUS POPUP (NO LEAK)
# =========================
def show_status_pop():
    global status_window

    remaining = max(0, int(RUN_TIME - (time.time() - START_TIME)))

    status_text = f"""
SYSTEM STATUS

Active   : {system_active}
Paused   : {system_paused}
Opened   : {already_opened}

Time Left : {remaining // 60} min {remaining % 60} sec

Hotkeys:
Ctrl+Alt+W = Open Apps
Ctrl+Alt+S = Reset
Ctrl+Alt+P = Pause
Ctrl+Alt+Q = Shutdown
Ctrl+Alt+I = Status
"""

    if status_window and status_window.winfo_exists():
        status_window.destroy()

    status_window = tk.Tk()
    status_window.title("System Status")
    status_window.geometry("360x300")
    status_window.resizable(False, False)

    label = tk.Label(status_window, text=status_text, font=("Consolas", 11), justify="left")
    label.pack(padx=15, pady=15)

    status_window.after(4000, status_window.destroy)
    status_window.mainloop()

# =========================
# ✅ AUTO KILL TIMER
# =========================
def auto_kill():
    while not shutdown_requested:
        if time.time() - START_TIME > RUN_TIME:
            write_log("Auto kill triggered")
            soft_shutdown()
            break
        time.sleep(10)  # ✅ ลด resource

def main():
    # =========================
    # ✅ HOTKEYS
    # =========================
    keyboard.add_hotkey('ctrl+alt+w', dev_mode)
    keyboard.add_hotkey('ctrl+alt+h', homr_mode)
    keyboard.add_hotkey('ctrl+alt+s', start_system)
    keyboard.add_hotkey('ctrl+alt+q', stop_system)
    keyboard.add_hotkey('ctrl+alt+p', toggle_paused)
    keyboard.add_hotkey('ctrl+alt+i', show_status_pop)

    # =========================
    # ✅ START SYSTEM
    # =========================
    write_log("System started")
    threading.Thread(target=auto_kill, daemon=True).start()
    keyboard.wait()

if  __name__ == "__main__":
    main()
