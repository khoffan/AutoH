import os
import subprocess

import psutil
from core.logger import write_log


def is_process_running(process_name):
    for proc in psutil.process_iter(["name"]):
        try:
            if proc.info["name"] and process_name.lower() in proc.info["name"].lower():
                return True
        except:
            pass
    return False


def safe_open_app(path, process_name):
    normalized_path = os.path.realpath(os.path.normpath(path)) if path else ""
    if not normalized_path:
        write_log(f"{process_name} path missing")
        return

    if not os.path.exists(normalized_path):
        write_log(f"{process_name} path invalid: {normalized_path}")
        return

    if not is_process_running(process_name):
        try:
            if normalized_path.lower().endswith(".lnk"):
                os.startfile(normalized_path)
            else:
                subprocess.Popen([normalized_path], shell=False)
            write_log(f"{process_name} opened")
        except Exception as exc:
            write_log(f"{process_name} launch failed: {exc}")
    else:
        write_log(f"{process_name} already running")


# ---------------------------------------------------------------- voice: open or focus
# Mode hotkeys use safe_open_app (never duplicate). A spoken "เปิด X" should behave
# like clicking the app icon: show the window if X is running, start X if not.

def _launch(path):
    if path.lower().endswith(".lnk") or not path.lower().endswith(".exe"):
        os.startfile(path)
    else:
        subprocess.Popen([path], shell=False, cwd=os.path.dirname(path))


def _app_pids(path, process_name):
    """PIDs that belong to the app: exe inside the launcher's folder, or name match.

    LINE starts from LINE\\bin\\LineLauncher.exe but runs as LINE\\bin\\current\\LINE.exe.
    """
    folder = os.path.normcase(os.path.dirname(path)) + os.sep if path.lower().endswith(".exe") else None
    name = process_name.lower().replace(" ", "")
    pids = set()
    for proc in psutil.process_iter(["pid", "name", "exe"]):
        try:
            exe = proc.info["exe"] or ""
            pname = (proc.info["name"] or "").lower()
            if folder and os.path.normcase(exe).startswith(folder):
                pids.add(proc.info["pid"])
            elif len(name) >= 3 and pname.replace(".exe", "") == name:
                pids.add(proc.info["pid"])
        except (psutil.Error, OSError):
            pass
    return pids


def _focus_window(pids):
    """Bring a visible top-level window of `pids` to the front. Returns True on success."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _lparam):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and user32.IsWindowVisible(hwnd) and not user32.GetWindow(hwnd, 4) \
                and user32.GetWindowTextLengthW(hwnd) > 0:          # 4 = GW_OWNER: skip popups
            found.append(hwnd)
            return False
        return True

    user32.EnumWindows(callback, 0)
    if not found:
        return False
    hwnd = found[0]
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)                                   # SW_RESTORE
    # Windows only lets the foreground app change focus; a synthetic Alt press
    # makes this process eligible (documented workaround for SetForegroundWindow).
    user32.keybd_event(0x12, 0, 0, 0)
    user32.keybd_event(0x12, 0, 2, 0)
    user32.SetForegroundWindow(hwnd)
    return True


def open_or_focus(path, process_name):
    """Show the app: focus its window if running and visible, otherwise (re)launch it.

    Relaunching a running single-instance app (LINE in the tray) makes it show its
    window, the same as clicking its icon. Returns "focused" or "opened".
    """
    from system.store_apps import is_packaged_path

    if is_packaged_path(path):
        # Store app (Notepad, Calculator...): no file on disk; Windows opens it by app id.
        normalized_path = path
        from voice.system import default as system_control

        pids = system_control().running_pids(path, process_name)
    else:
        normalized_path = os.path.realpath(os.path.normpath(path)) if path else ""
        if not normalized_path or not os.path.exists(normalized_path):
            raise FileNotFoundError(f"ไม่พบไฟล์โปรแกรม: {path}")
        pids = _app_pids(normalized_path, process_name)
    if pids and _focus_window(pids):
        write_log(f"{process_name} focused")
        return "focused"
    _launch(normalized_path)
    write_log(f"{process_name} {'shown (was running)' if pids else 'opened'}")
    return "opened"
