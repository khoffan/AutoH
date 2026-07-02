import os
import re
import winreg


def get_apps_from_registry():
    apps = []

    reg_paths = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        r"SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
    ]

    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for path in reg_paths:
            try:
                with winreg.OpenKey(root, path) as key:
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, subkey_name) as subkey:
                                # ดึง DisplayName
                                try:
                                    name, _ = winreg.QueryValueEx(subkey, "DisplayName")
                                except Exception:
                                    continue  # ถ้าไม่มีชื่อแอป ข้ามไปเลย

                                if not name:
                                    continue

                                # 1. พยายามดึง InstallLocation (โฟลเดอร์ติดตั้งหลัก)
                                install_location = ""
                                try:
                                    install_location, _ = winreg.QueryValueEx(
                                        subkey, "InstallLocation"
                                    )
                                except Exception:
                                    pass

                                # 2. ดึง DisplayIcon มาเป็นทางเลือกสำรอง
                                display_icon = ""
                                try:
                                    display_icon, _ = winreg.QueryValueEx(subkey, "DisplayIcon")
                                    # คลีนพวก ",0" หรือ引號ออก (เช่น "C:\App.exe",0 -> C:\App.exe)
                                    display_icon = re.sub(r",[-\d]+$", "", display_icon).strip('"')
                                except Exception:
                                    pass

                                exe_path = ""

                                # --- LOGIC ค้นหาตัวรันแอปที่แท้จริง ---
                                # เคสพิเศษอย่าง Docker Desktop: ถ้าได้ DisplayIcon เป็น Installer แต่อยากได้ตัวแอปหลัก
                                if (
                                    display_icon
                                    and "installer" in os.path.basename(display_icon).lower()
                                ):
                                    # ลองเดาใจเปลี่ยนชื่อไฟล์ตรงๆ ในโฟลเดอร์เดียวกันก่อน
                                    guessed_exe = (
                                        display_icon.lower()
                                        .replace(" installer.exe", ".exe")
                                        .replace("installer.exe", ".exe")
                                    )
                                    if os.path.exists(guessed_exe):
                                        exe_path = guessed_exe

                                # ถ้าเคสทั่วไป หรือสเต็ปบนยังไม่ได้ผล แต่มี InstallLocation
                                if (
                                    not exe_path
                                    and install_location
                                    and os.path.exists(install_location)
                                ):
                                    # ลองหาไฟล์ .exe ที่ชื่อเดียวกับแอป หรือไฟล์หลักในโฟลเดอร์นั้น
                                    possible_exe = os.path.join(install_location, f"{name}.exe")
                                    if os.path.exists(possible_exe):
                                        exe_path = possible_exe
                                    else:
                                        # ถ้าหาไม่เจอจริงๆ ค่อยคุ้ยในโฟลเดอร์นั้นหาไฟล์ .exe ตัวแรกที่ไม่ใช่คำว่า installer/setup
                                        for root_dir, _, files in os.walk(install_location):
                                            exe_files = [
                                                f
                                                for f in files
                                                if f.endswith(".exe")
                                                and "installer" not in f.lower()
                                                and "setup" not in f.lower()
                                            ]
                                            if exe_files:
                                                exe_path = os.path.join(root_dir, exe_files[0])
                                                break

                                # ต่ำสุดถ้าไม่มีอะไรเลยจริงๆ ค่อยยอมใช้ DisplayIcon (ที่แอปทั่วไปมักจะใส่เป็นตัว .exe หลักไว้)
                                if (
                                    not exe_path
                                    and display_icon
                                    and display_icon.lower().endswith(".exe")
                                ):
                                    exe_path = display_icon

                                # บันทึกผลลัพธ์
                                apps.append({"name": name.strip(), "exe": exe_path})
                        except Exception:
                            pass
            except Exception:
                pass

    return apps
