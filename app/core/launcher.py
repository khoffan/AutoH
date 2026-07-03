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
