import psutil
import subprocess
import os
from core.logger import write_log



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