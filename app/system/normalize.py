import os


def normalize_apps(reg_apps, menu_apps):
    app_dict = {}

    # คำที่ถ้าเจอใน "ชื่อแอป" หรือ "ชื่อไฟล์ .exe ตัวท้ายสุด" ให้ตัดทิ้งทันที
    STRICT_INSTALLER_WORDS = {"installer", "setup", "uninstall", "uninst", "patcher"}

    print(f"Normalizing apps: {len(reg_apps)} from registry, {len(menu_apps)} from start menu")

    def has_valid_path(app):
        path = app.get("path") or app.get("exe_path") or app.get("uninstall_string", "")
        return bool(path and path.strip())

    for app in menu_apps + reg_apps:
        name = app.get("name", "").strip()
        if not name:
            continue

        raw_path = app.get("path") or app.get("exe_path") or app.get("uninstall_string", "")
        app_name_lower = name.lower()

        # แยกเฉพาะชื่อไฟล์ตัวท้ายสุดออกมาจาก Path (เช่น ได้ "Docker Desktop Installer.exe")
        filename = os.path.basename(raw_path).lower() if raw_path else ""

        # --- LOGIC การกรองตัวติดตั้งที่แม่นยำขึ้น ---
        is_installer = False

        # 1. เช็คจากชื่อแอปตรงๆ
        if any(word in app_name_lower for word in STRICT_INSTALLER_WORDS):
            is_installer = True

        # 2. เช็คที่ชื่อไฟล์ .exe ตัวท้ายสุด (ไม่เอาชื่อโฟลเดอร์ข้างหน้ามาเกี่ยว)
        # วิธีนี้จะทำให้ "Docker Desktop.exe" รอด แต่ "Docker Desktop Installer.exe" จะโดนบล็อก
        elif filename and any(word in filename for word in STRICT_INSTALLER_WORDS):
            is_installer = True

        if is_installer:
            print(f"--> [Filtered Out] Installer/Uninstaller detected: {name} ({raw_path})")
            continue
        # ----------------------------------------

        key = app_name_lower

        if key not in app_dict:
            app_dict[key] = app.copy()
        else:
            existing_app = app_dict[key]
            if not has_valid_path(existing_app) and has_valid_path(app):
                existing_app.update(app)
            else:
                for k, v in app.items():
                    if v and not existing_app.get(k):
                        existing_app[k] = v

    return list(app_dict.values())
