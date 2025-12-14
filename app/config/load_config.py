import os
import sys
import json
from config.get_base_dir import get_base_dir
# =========================
# ✅ LOAD CONFIG (SAFE)
# =========================
def load_config():
    basedir = get_base_dir()

    CONFIG_PATH = os.path.join(basedir, "config.json")

    if not os.path.exists(CONFIG_PATH):
        print("❌ config.json not found:", CONFIG_PATH)
        input("Press Enter to exit...")
        sys.exit(1)

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cf = json.load(f)
    return cf