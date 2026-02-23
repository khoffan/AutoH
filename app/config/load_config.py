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

def save_config_file(mode_name, hotkey, app_list, urls=""):
    config_path = 'config.json'
    
    # อ่านไฟล์เดิมก่อน (ถ้ามี)
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except:
        data = {"modes": {}}

    # เตรียมข้อมูลแอปในรูปแบบที่โปรแกรมหลักใช้
    app_mapping = {app["name"]: (app.get("path") or app.get("exe")) for app in app_list}

    # เพิ่มหรืออัปเดตโหมด
    mode_data = {
        "hotkey": hotkey,
        "apps": app_mapping
    }
    if urls:
        mode_data["urls"] = urls
    data["modes"][mode_name] = mode_data

    # บันทึกกลับลงไฟล์
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)