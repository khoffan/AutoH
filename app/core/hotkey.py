import time
import webbrowser
import keyboard
import threading
import psutil
import os
from core.logger import write_log
from core.launcher import safe_open_app
from config.load_config import load_config
from ui.status import show_status_pop

cf = load_config()
RUN_TIME      = cf.get("run_time_minute", 20) * 60
DEBOUNCE_SECOND = cf.get("debounce_second", 2)

START_TIME = time.time()
system_active = True
system_paused = False
already_opened = False
shutdown_requested = False
last_press_time = 0
status_window = None
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

def auto_kill():
    global shutdown_requested
    while not shutdown_requested:
        if time.time() - START_TIME > RUN_TIME:
            write_log("Auto kill triggered")
            soft_shutdown()
            break
        time.sleep(10)  # ✅ ลด resource


def dev_mode():
    global already_opened, last_press_time
    dev_cf = cf.get("dev", "")
    BROWSER_URL     = dev_cf.get("browser", "https://www.google.com")
    ANTIGRAVITY     = dev_cf.get("antigravity", "")
    POSTMAN_PATH   = dev_cf.get("postman", "")
    SLACK_PATH     = dev_cf.get("slack", "")
    MONGODB_PATH   = dev_cf.get("mongodb", "")
    

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

def home_mode():
    global already_opened, last_press_time
    dev_cf = cf.get("home", "")
    BROWSER_URL     = dev_cf.get("browser", "https://www.google.com")

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
        if len(BROWSER_URL) > 2:
            for url in BROWSER_URL.split(","):
                webbrowser.open(url.strip())
        else:
            webbrowser.open("https://www.google.com")
    except Exception as e:
        write_log("Open error: " + str(e))


def start_hotkey_listener():
    # =========================
    # ✅ HOTKEYS
    # =========================
    keyboard.add_hotkey('ctrl+alt+w', dev_mode)
    keyboard.add_hotkey('ctrl+alt+h', home_mode)
    keyboard.add_hotkey('ctrl+alt+s', start_system)
    keyboard.add_hotkey('ctrl+alt+q', stop_system)
    keyboard.add_hotkey('ctrl+alt+p', toggle_paused)
    
    keyboard.add_hotkey('ctrl+alt+i', show_status_pop(start_time=START_TIME, runtime=RUN_TIME, system_active=system_active, system_paused=system_paused, already_opened=already_opened, status_window=status_window))

    # =========================
    # ✅ START SYSTEM
    # =========================
    write_log("System started")
    threading.Thread(target=auto_kill, daemon=True).start()
    keyboard.wait()
