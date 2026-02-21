from datetime import datetime
from config.load_log_file import load_logfile

LOG_FILE = load_logfile()

def write_log(msg):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{now} - {msg}\n")