from __future__ import annotations

import queue
import time
import webbrowser
from dataclasses import dataclass, field

import customtkinter as ctk
import keyboard
from config.load_config import load_config
from core.launcher import safe_open_app
from core.logger import write_log
from ui.selected_app import get_user_configuration
from ui.status import StatusSnapshot, show_status_window
from ui.theme import APP_THEME

RUN_TIME = 20 * 60
DEBOUNCE_SECOND = 2


@dataclass
class RuntimeState:
    start_time: float = field(default_factory=time.time)
    system_active: bool = True
    system_paused: bool = False
    already_opened: bool = False
    shutdown_requested: bool = False
    last_press_by_mode: dict[str, float] = field(default_factory=dict)


class AutoHController(ctk.CTk):
    def __init__(self):
        ctk.set_appearance_mode(APP_THEME["appearance_mode"])
        ctk.set_default_color_theme("blue")
        super().__init__(fg_color=APP_THEME["window_bg"])

        self.withdraw()
        self.title("AutoH")
        self.runtime = RuntimeState()
        self.task_queue = queue.Queue()
        self.config_window = None
        self.status_window = None
        self.mode_hotkey_ids = []
        self.modes = {}

        self.protocol("WM_DELETE_WINDOW", self.stop_system)
        self.reload_modes()
        self.register_static_hotkeys()
        self.after(100, self.process_tasks)
        self.after(1000, self.check_runtime)

    def run(self):
        write_log("System started")
        if not self.modes:
            self.after(50, lambda: self.open_config_ui(startup=True))
        self.mainloop()

    def request_task(self, func, *args):
        self.task_queue.put((func, args))

    def process_tasks(self):
        if self.runtime.shutdown_requested:
            return

        while True:
            try:
                func, args = self.task_queue.get_nowait()
            except queue.Empty:
                break

            try:
                func(*args)
            except Exception as exc:
                write_log(f"Task error: {exc}")

        self.after(100, self.process_tasks)

    def check_runtime(self):
        if self.runtime.shutdown_requested:
            return

        if time.time() - self.runtime.start_time > RUN_TIME:
            write_log("Auto shutdown triggered")
            self.show_status_ui("Runtime reached the automatic shutdown limit.")
            self.stop_system()
            return

        self.after(1000, self.check_runtime)

    def reload_modes(self):
        config = load_config(default={"modes": {}}, exit_on_missing=False)
        self.modes = config.get("modes", {})
        self.register_mode_hotkeys()

    def register_static_hotkeys(self):
        keyboard.add_hotkey("ctrl+alt+s", lambda: self.request_task(self.start_system))
        keyboard.add_hotkey("ctrl+alt+q", lambda: self.request_task(self.stop_system))
        keyboard.add_hotkey("ctrl+alt+p", lambda: self.request_task(self.toggle_paused))
        keyboard.add_hotkey("ctrl+alt+e", lambda: self.request_task(self.open_config_ui, False))
        keyboard.add_hotkey(
            "ctrl+alt+i", lambda: self.request_task(self.show_status_ui, "System state overview")
        )

    def register_mode_hotkeys(self):
        for hotkey_id in self.mode_hotkey_ids:
            try:
                keyboard.remove_hotkey(hotkey_id)
            except KeyError:
                pass
        self.mode_hotkey_ids.clear()

        for mode_name, settings in self.modes.items():
            hotkey = settings.get("hotkey")
            if not hotkey:
                continue

            try:
                hotkey_id = keyboard.add_hotkey(
                    hotkey,
                    lambda selected_mode=mode_name: self.request_task(
                        self.launch_apps_mode, selected_mode
                    ),
                )
                self.mode_hotkey_ids.append(hotkey_id)
            except ValueError as exc:
                write_log(f"Skipping invalid hotkey '{hotkey}' for mode '{mode_name}': {exc}")

    def build_status_snapshot(self):
        return StatusSnapshot(
            runtime=RUN_TIME,
            start_time=self.runtime.start_time,
            system_active=self.runtime.system_active,
            system_paused=self.runtime.system_paused,
            already_opened=self.runtime.already_opened,
            modes=self.modes,
        )

    def show_status_ui(self, message="System state overview"):
        self.status_window = show_status_window(
            self,
            snapshot=self.build_status_snapshot(),
            existing_window=self.status_window,
            message=message,
        )

    def open_config_ui(self, startup=False):
        if self.config_window is not None and self.config_window.winfo_exists():
            self.config_window.focus_window()
            return

        self.config_window = get_user_configuration(
            self,
            on_modes_changed=self.on_modes_changed,
            on_close=lambda has_modes: self.on_config_close(has_modes, startup),
            startup=startup,
        )

    def on_modes_changed(self, modes, message):
        self.modes = modes
        self.register_mode_hotkeys()
        write_log(message)
        self.show_status_ui(message)

    def on_config_close(self, has_modes, startup):
        self.config_window = None
        self.reload_modes()

        if startup and not has_modes:
            write_log("No mode configured during startup. Shutting down.")
            self.stop_system()
            return

        if startup and has_modes:
            self.show_status_ui("Configuration ready. AutoH is listening for hotkeys.")

    def start_system(self):
        self.runtime.already_opened = False
        self.runtime.system_active = True
        self.runtime.system_paused = False
        write_log("System reset")
        self.show_status_ui("System reset. Mode launch is available again.")

    def toggle_paused(self):
        self.runtime.system_paused = not self.runtime.system_paused
        write_log(f"Paused: {self.runtime.system_paused}")
        message = (
            "System paused. Mode hotkeys are temporarily blocked."
            if self.runtime.system_paused
            else "System resumed. Mode hotkeys are active again."
        )
        self.show_status_ui(message)

    def stop_system(self):
        if self.runtime.shutdown_requested:
            return

        self.runtime.shutdown_requested = True
        write_log("Shutdown requested")

        try:
            keyboard.unhook_all()
        except Exception as exc:
            write_log(f"Hotkey cleanup error: {exc}")

        if self.config_window is not None and self.config_window.winfo_exists():
            self.config_window.destroy()
        if self.status_window is not None and self.status_window.winfo_exists():
            self.status_window.destroy()

        self.quit()
        self.destroy()

    def launch_apps_mode(self, mode_name):
        now = time.time()
        last_pressed = self.runtime.last_press_by_mode.get(mode_name, 0)
        if now - last_pressed < DEBOUNCE_SECOND:
            return

        self.runtime.last_press_by_mode[mode_name] = now

        if (
            self.runtime.system_paused
            or not self.runtime.system_active
            or self.runtime.already_opened
        ):
            write_log(f"Blocked: System state not ready for {mode_name}")
            return

        mode_config = self.modes.get(mode_name, {})
        if not mode_config:
            write_log(f"Config for {mode_name} not found")
            return

        self.runtime.already_opened = True
        write_log(f"MODE: {mode_name} triggered")

        try:
            urls = mode_config.get("urls", "")
            if urls:
                for url in [part.strip() for part in urls.split(",") if part.strip()]:
                    webbrowser.open(url)

            for app_name, app_path in mode_config.get("apps", {}).items():
                if app_path:
                    safe_open_app(app_path, app_name)

            write_log(f"All apps for {mode_name} handled")
        except Exception as exc:
            write_log(f"Error in {mode_name}: {exc}")


def start_hotkey_listener():
    app = AutoHController()
    app.run()
