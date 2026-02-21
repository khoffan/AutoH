import tkinter as tk
import sys
from tkinter import simpledialog
from config.load_config import save_config_file, load_config
from system.normalize import normalize_apps
from system.registry import get_apps_from_registry
from system.start_menus import get_apps_from_start_menu

def on_closing(root):
    root.destroy()
    sys.exit()



def select_apps_ui(apps, existing_hotkeys):
    main_root = tk.Tk()      # สร้างหน้าต่างหลัก
    main_root.withdraw()     # สั่งซ่อนหน้าต่างหลักทันที (กล่องว่างจะหายไป)
    
    selected_apps = []
    filtered_apps = apps.copy()

    # ดักจับถ้ามีการปิดหน้าต่างหลัก (เผื่อไว้)
    main_root.protocol("WM_DELETE_WINDOW", lambda: on_closing(main_root))

    root = tk.Toplevel() # ใช้ Toplevel แทน Tk ถ้าเรียกจาก main window
    root.title("Hotkey Mode Setup")
    root.geometry("900x700")

    # --- ส่วนที่เพิ่ม: ดักจับการกดปุ่ม X ที่หน้าต่าง Setup ---
    root.protocol("WM_DELETE_WINDOW", lambda: on_closing(main_root))
    # --- ส่วนที่ 1: การจัดการข้อมูล ---
    def on_search(*_):
        nonlocal filtered_apps
        kw = search_var.get().lower()
        filtered_apps = [a for a in apps if kw in a["name"].lower()] if kw else apps.copy()
        refresh_source_list()

    def add_to_basket():
        for i in lb_source.curselection():
            app = filtered_apps[i]
            if app not in selected_apps:
                selected_apps.append(app)
        refresh_basket_list()

    def remove_from_basket():
        indices = list(lb_basket.curselection())
        for i in reversed(indices):
            selected_apps.pop(i)
        refresh_basket_list()

    def refresh_source_list():
        lb_source.delete(0, tk.END)
        for app in filtered_apps:
            lb_source.insert(tk.END, f" {app['name']}")

    def refresh_basket_list():
        lb_basket.delete(0, tk.END)
        for app in selected_apps:
            lb_basket.insert(tk.END, f" ✅ {app['name']}")

    # --- ส่วนที่ 2: ระบบตรวจสอบ (Validation) ---
    def validate_and_confirm():
        mode_name = ent_mode.get().strip()
        hotkey = ent_hk.get().strip().lower()
        urls = ent_urls.get().strip()

        # 1. เช็คความว่างเปล่า
        if not mode_name or not hotkey:
            messagebox.showerror("Error", "กรุณากรอกชื่อ Mode และ Hotkey")
            return

        # 2. เช็ค Hotkey ซ้ำกับระบบ
        system_keys = ['ctrl+alt+s', 'ctrl+alt+q', 'ctrl+alt+p', 'ctrl+alt+i']
        if hotkey in system_keys:
            messagebox.showerror("Error", f"Hotkey {hotkey} ถูกจองโดยระบบแล้ว")
            return

        # 3. เช็ค Hotkey ซ้ำกับที่มีอยู่เดิม
        if hotkey in existing_hotkeys:
            messagebox.showerror("Error", f"Hotkey {hotkey} มีการใช้งานอยู่แล้ว")
            return

        # ถ้าผ่านทุกอย่าง
        result_data = {
            "mode_name": mode_name,
            "hotkey": hotkey,
            "urls": urls,
            "apps": selected_apps
        }
        root.final_data = result_data
        root.destroy()

    # --- ส่วนที่ 3: จัดวาง UI Layout ---
    # ฝั่งซ้าย: ค้นหาแอป
    frame_left = tk.LabelFrame(root, text=" 1. Search & Select Apps ", padx=10, pady=10)
    frame_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

    search_var = tk.StringVar()
    search_var.trace_add("write", on_search)
    tk.Entry(frame_left, textvariable=search_var).pack(fill=tk.X, pady=5)
    
    lb_source = tk.Listbox(frame_left, selectmode=tk.MULTIPLE)
    lb_source.pack(fill=tk.BOTH, expand=True)
    refresh_source_list()
    
    tk.Button(frame_left, text="Add Selected >>", command=add_to_basket, bg="#e1f5fe").pack(fill=tk.X, pady=5)

    # ฝั่งขวา: สรุปรายการและตั้งค่า
    frame_right = tk.LabelFrame(root, text=" 2. Mode Settings ", padx=10, pady=10)
    frame_right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

    tk.Label(frame_right, text="Apps in this mode:").pack(anchor=tk.W)
    lb_basket = tk.Listbox(frame_right, height=10)
    lb_basket.pack(fill=tk.X, pady=5)
    tk.Button(frame_right, text="Remove Selected", command=remove_from_basket).pack(anchor=tk.E)

    tk.Label(frame_right, text="Mode Name (e.g. Work):").pack(anchor=tk.W, pady=(10,0))
    ent_mode = tk.Entry(frame_right)
    ent_mode.pack(fill=tk.X)

    tk.Label(frame_right, text="Hotkey (e.g. ctrl+alt+w):").pack(anchor=tk.W, pady=(10,0))
    ent_hk = tk.Entry(frame_right)
    ent_hk.insert(0, "ctrl+alt+")
    ent_hk.pack(fill=tk.X)

    tk.Label(frame_right, text="URLs (separate by comma):").pack(anchor=tk.W, pady=(10,0))
    ent_urls = tk.Entry(frame_right)
    ent_urls.pack(fill=tk.X)

    tk.Button(frame_right, text="CONFIRM & SAVE", command=validate_and_confirm, 
              bg="#4caf50", fg="white", font=('Helvetica', 10, 'bold')).pack(fill=tk.X, pady=20)

    root.final_data = None
    root.wait_window()

    main_root.destroy()
    return root.final_data

def get_user_configuration():
    # โหลด config ปัจจุบันเพื่อเอาไปเช็ค hotkey ซ้ำ
    current_cf = load_config()
    existing_hotkeys = [m.get("hotkey") for m in current_cf.get("modes", {}).values()]

    all_apps = normalize_apps(get_apps_from_registry(), get_apps_from_start_menu())
    
    # เปิด UI ใหม่
    config_result = select_apps_ui(all_apps, existing_hotkeys)
    
    if config_result:
        # แยกข้อมูลไปบันทึก
        save_config_file(
            config_result["mode_name"], 
            config_result["hotkey"], 
            config_result["apps"],
            config_result["urls"]
        )
        messagebox.showinfo("Success", f"Saved {config_result['mode_name']} successfully!")