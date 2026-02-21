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


RUN_TIME      =  20 * 60
DEBOUNCE_SECOND = 2

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
    show_status_pop(start_time=START_TIME, runtime=RUN_TIME, system_active=system_active, system_paused=system_paused, already_opened=already_opened, status_window=status_window)

def start_system():
    global already_opened, system_active
    already_opened = False
    system_active = True
    write_log("System reset")
    show_status_pop(start_time=START_TIME, runtime=RUN_TIME, system_active=system_active, system_paused=system_paused, already_opened=already_opened, status_window=status_window)

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


def launch_apps_mode(mode_name, cf):
    global already_opened, last_press_time
    
    # 1. Check Debounce
    now = time.time()
    if now - last_press_time < DEBOUNCE_SECOND:
        return
    last_press_time = now

    # 2. Check System Status
    if system_paused or not system_active or already_opened:
        write_log(f"Blocked: System state not ready for {mode_name}")
        return

    # 3. Load Config ตาม mode_name ที่ส่งมา (เช่น 'dev', 'home' หรือชื่อใหม่ๆ)
    mode_cf = cf.get(mode_name, {})
    if not mode_cf:
        write_log(f"Config for {mode_name} not found")
        return

    already_opened = True
    write_log(f"MODE: {mode_name} triggered")

    try:
        # เปิด Browser (รองรับทั้ง string เดี่ยว และ comma-separated)
        urls = mode_cf.get("browser", "")
        if(urls != ""):
            for url in (urls.split(",") if "," in urls else [urls]):
                webbrowser.open(url.strip())

        # เปิด Apps อื่นๆ ที่ระบุใน Config
        # 2. เปิด Apps (ดึงจาก key "apps" ที่เราออกแบบไว้)
        apps_to_open = mode_cf.get("apps", {})
        for app_name, app_path in apps_to_open.items():
            if app_path:
                safe_open_app(app_path, app_name)

        write_log(f"All apps for {mode_name} handled")
    except Exception as e:
        write_log(f"Error in {mode_name}: {str(e)}")


def start_hotkey_listener():
    
    cf = load_config()
    modes = cf.get("modes", {})
    # =========================
    # ✅ HOTKEYS
    # =========================
    for mode_name, settings in modes.items():
        hk = settings.get("hotkey")
        if hk:
            # ส่งแค่ mode_name เข้าไป launch_apps_mode จะไปอ่านแอปต่อเอง
            print(mode_name, hk)
            keyboard.add_hotkey(hk, lambda m=mode_name: launch_apps_mode(m, modes))
    keyboard.add_hotkey('ctrl+alt+s', start_system)
    keyboard.add_hotkey('ctrl+alt+q', stop_system)
    keyboard.add_hotkey('ctrl+alt+p', toggle_paused)
    
    keyboard.add_hotkey('ctrl+alt+i', lambda: show_status_pop(start_time=START_TIME, runtime=RUN_TIME, system_active=system_active, system_paused=system_paused, already_opened=already_opened, status_window=status_window))

    # =========================
    # ✅ START SYSTEM
    # =========================
    write_log("System started")
    threading.Thread(target=auto_kill, daemon=True).start()
    keyboard.wait()
