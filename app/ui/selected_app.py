import sys
import os
import asyncio
import threading
import subprocess
import flet as ft
from config.load_config import save_config_file, load_config
from system.normalize import normalize_apps
from system.registry import get_apps_from_registry
from system.start_menus import get_apps_from_start_menu


def select_apps_ui(apps, existing_hotkeys):
    """Open Flet UI for selecting apps and configuring a hotkey mode.
    Returns a dict with mode_name, hotkey, urls, apps — or None if cancelled.
    """
    final_data = [None]  # mutable container so inner function can write to it

    async def main(page: ft.Page):
        page.title = "Hotkey Mode Setup"
        page.theme_mode = ft.ThemeMode.DARK
        page.window.width = 950
        page.window.height = 700
        page.padding = 20

        # --- Close-window handler ---
        async def on_window_event(e):
            if e.type == ft.WindowEventType.CLOSE:
                page.window.prevent_close = False
                await page.window.close()

        page.window.prevent_close = True
        page.window.on_event = on_window_event

        # --- Local State ---
        selected_apps = []
        filtered_apps = apps.copy()

        # --- Flet Controls ---
        search_field = ft.TextField(
            label="Search apps…",
            prefix_icon=ft.Icons.SEARCH,
            border_radius=8,
            on_change=lambda e: on_search(),
        )

        source_list = ft.ListView(expand=True, spacing=2, padding=10)
        basket_list = ft.ListView(expand=True, spacing=2, padding=10)

        ent_mode = ft.TextField(label="Mode Name (e.g. Work)", border_radius=8)
        ent_hk = ft.TextField(
            label="Hotkey (e.g. ctrl+alt+w)", value="ctrl+alt+", border_radius=8
        )
        ent_urls = ft.TextField(label="URLs (separate by comma)", border_radius=8)

        # Track which source items are selected (indices)
        selected_source_indices: set = set()

        # --- ส่วนที่ 1: การจัดการข้อมูล (Data Logic — unchanged) ---
        def on_search(*_):
            nonlocal filtered_apps
            kw = search_field.value.lower() if search_field.value else ""
            filtered_apps = (
                [a for a in apps if kw in a["name"].lower()] if kw else apps.copy()
            )
            selected_source_indices.clear()
            refresh_source_list()

        def add_to_basket(e=None):
            for i in sorted(selected_source_indices):
                app = filtered_apps[i]
                if app not in selected_apps:
                    selected_apps.append(app)
            selected_source_indices.clear()
            refresh_source_list()
            refresh_basket_list()

        def remove_from_basket(index):
            if 0 <= index < len(selected_apps):
                selected_apps.pop(index)
            refresh_basket_list()

        def refresh_source_list():
            source_list.controls.clear()
            for idx, app in enumerate(filtered_apps):
                is_selected = idx in selected_source_indices
                tile = ft.ListTile(
                    leading=ft.Checkbox(
                        value=is_selected,
                        on_change=lambda e, i=idx: toggle_source(i, e.control.value),
                    ),
                    title=ft.Text(app["name"], size=14),
                    on_click=lambda e, i=idx: toggle_source_click(i),
                    dense=True,
                    bgcolor=(
                        ft.Colors.with_opacity(0.15, ft.Colors.BLUE)
                        if is_selected
                        else None
                    ),
                    shape=ft.RoundedRectangleBorder(radius=6),
                )
                source_list.controls.append(tile)
            page.update()

        def toggle_source(index, value):
            if value:
                selected_source_indices.add(index)
            else:
                selected_source_indices.discard(index)
            refresh_source_list()

        def toggle_source_click(index):
            if index in selected_source_indices:
                selected_source_indices.discard(index)
            else:
                selected_source_indices.add(index)
            refresh_source_list()

        def refresh_basket_list():
            basket_list.controls.clear()
            for idx, app in enumerate(selected_apps):
                tile = ft.ListTile(
                    leading=ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN_400),
                    title=ft.Text(app["name"], size=14),
                    trailing=ft.IconButton(
                        ft.Icons.DELETE_OUTLINE,
                        icon_color=ft.Colors.RED_300,
                        tooltip="Remove",
                        on_click=lambda e, i=idx: remove_from_basket(i),
                    ),
                    dense=True,
                    shape=ft.RoundedRectangleBorder(radius=6),
                )
                basket_list.controls.append(tile)
            page.update()

        # --- ส่วนที่ 2: ระบบตรวจสอบ (Validation — unchanged logic) ---
        def show_snackbar(message, is_error=True):
            page.overlay.clear()
            snack = ft.SnackBar(
                content=ft.Text(
                    message,
                    color=ft.Colors.WHITE,
                    weight=ft.FontWeight.W_500,
                ),
                bgcolor=ft.Colors.RED_700 if is_error else ft.Colors.GREEN_700,
                duration=3000,
            )
            page.overlay.append(snack)
            snack.open = True
            page.update()

        async def validate_and_confirm(e=None):
            mode_name = ent_mode.value.strip() if ent_mode.value else ""
            hotkey = ent_hk.value.strip().lower() if ent_hk.value else ""
            urls = ent_urls.value.strip() if ent_urls.value else ""

            # 1. เช็คความว่างเปล่า
            if not mode_name or not hotkey:
                show_snackbar("กรุณากรอกชื่อ Mode และ Hotkey")
                return

            # 2. เช็ค Hotkey ซ้ำกับระบบ
            system_keys = ["ctrl+alt+s", "ctrl+alt+q", "ctrl+alt+p", "ctrl+alt+i"]
            if hotkey in system_keys:
                show_snackbar(f"Hotkey {hotkey} ถูกจองโดยระบบแล้ว")
                return

            # 3. เช็ค Hotkey ซ้ำกับที่มีอยู่เดิม
            if hotkey in existing_hotkeys:
                show_snackbar(f"Hotkey {hotkey} มีการใช้งานอยู่แล้ว")
                return

            # 4. เช็ค Hotkey ว่าเป็นคีย์ที่ถูกต้องหรือไม่
            try:
                import keyboard
                keyboard.parse_hotkey(hotkey)
            except (ValueError, ImportError):
                show_snackbar(f"Hotkey '{hotkey}' ไม่ถูกต้อง — ใช้เฉพาะปุ่มจริงเช่น ctrl+alt+w")
                return

            # ถ้าผ่านทุกอย่าง
            result_data = {
                "mode_name": mode_name,
                "hotkey": hotkey,
                "urls": urls,
                "apps": selected_apps,
            }
            final_data[0] = result_data
            page.window.prevent_close = False
            await page.window.close()

        # --- ส่วนที่ 3: จัดวาง UI Layout ---
        # Left panel — Search & Source
        left_panel = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "1. Search & Select Apps",
                        size=16,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.BLUE_200,
                    ),
                    search_field,
                    ft.Container(
                        content=source_list,
                        border=ft.border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE)),
                        border_radius=8,
                        expand=True,
                    ),
                    ft.ElevatedButton(
                        "Add Selected >>",
                        icon=ft.Icons.ADD_CIRCLE_OUTLINE,
                        on_click=add_to_basket,
                        bgcolor=ft.Colors.BLUE_700,
                        color=ft.Colors.WHITE,
                        width=float("inf"),
                    ),
                ],
                spacing=10,
                expand=True,
            ),
            expand=True,
            padding=15,
            border_radius=12,
            border=ft.border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.WHITE)),
            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.WHITE),
        )

        # Right panel — Settings & Basket
        right_panel = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "2. Mode Settings",
                        size=16,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.GREEN_200,
                    ),
                    ft.Text("Apps in this mode:", size=13, color=ft.Colors.WHITE70),
                    ft.Container(
                        content=basket_list,
                        border=ft.border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE)),
                        border_radius=8,
                        height=220,
                    ),
                    ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
                    ent_mode,
                    ent_hk,
                    ent_urls,
                    ft.Container(height=10),
                    ft.ElevatedButton(
                        "CONFIRM & SAVE",
                        icon=ft.Icons.SAVE_ALT,
                        on_click=validate_and_confirm,
                        bgcolor=ft.Colors.GREEN_700,
                        color=ft.Colors.WHITE,
                        width=float("inf"),
                        height=50,
                    ),
                ],
                spacing=10,
                expand=True,
            ),
            expand=True,
            padding=15,
            border_radius=12,
            border=ft.border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.WHITE)),
            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.WHITE),
        )

        page.add(
            ft.Row(
                [left_panel, right_panel],
                expand=True,
                spacing=15,
            )
        )

        # Initial data load
        refresh_source_list()

    # --- Run Flet app (blocking, like root.wait_window()) ---
    ft.app(target=main)
    return final_data[0]


def _run_configuration():
    """Core logic: open UI, validate, save config. Must run in main thread."""
    current_cf = load_config()
    existing_hotkeys = [m.get("hotkey") for m in current_cf.get("modes", {}).values()]

    all_apps = normalize_apps(get_apps_from_registry(), get_apps_from_start_menu())

    # เปิด UI ใหม่
    config_result = select_apps_ui(all_apps, existing_hotkeys)

    if not config_result:
        # ผู้ใช้กดปิดหน้าต่าง (X) โดยไม่ได้บันทึก
        print("❌ Configuration cancelled.")
        sys.exit()

    # แยกข้อมูลไปบันทึก
    save_config_file(
        config_result["mode_name"],
        config_result["hotkey"],
        config_result["apps"],
        config_result["urls"],
    )
    print(f"✅ Saved {config_result['mode_name']} successfully!")


def get_user_configuration():
    """Open the config UI. If called from a hotkey thread, spawns a subprocess."""
    if threading.current_thread() is threading.main_thread():
        # Called from main thread (e.g. startup) — run directly
        _run_configuration()
    else:
        # Called from keyboard hotkey thread — Flet needs its own main thread
        app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        subprocess.Popen(
            [
                sys.executable, "-c",
                f"import sys; sys.path.insert(0, r'{app_root}'); "
                "from ui.selected_app import _run_configuration; _run_configuration()"
            ],
            cwd=app_root,
        )


def show_snackbar_standalone(message):
    """Quick standalone success notification after main UI has closed."""

    async def _notify(page: ft.Page):
        page.title = "AutoH"
        page.theme_mode = ft.ThemeMode.DARK
        page.window.width = 400
        page.window.height = 150
        page.add(
            ft.Container(
                content=ft.Column(
                    [
                        ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN_400, size=40),
                        ft.Text(message, size=16, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=10,
                ),
                alignment=ft.Alignment(0, 0),
                expand=True,
            )
        )
        page.window.always_on_top = True
        await asyncio.sleep(2)
        await page.window.close()

    ft.app(target=_notify)