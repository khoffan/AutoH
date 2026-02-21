import os
import sys
from config.get_base_dir import get_base_dir
def load_logfile():
    basedir = get_base_dir()

    LOG_FILE = os.path.join(basedir, "log.txt")

    return LOG_FILE