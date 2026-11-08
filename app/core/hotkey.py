from __future__ import annotations

import queue
import sqlite3
import time
import webbrowser
from dataclasses import dataclass, field

import customtkinter as ctk
import keyboard
from config import database
from config.load_config import load_config
from core.launcher import safe_open_app
from core.logger import write_log
from ui.selected_app import get_user_configuration
from ui.status import StatusSnapshot, show_status_window
from ui.theme import APP_THEME
from ui.tray import TrayActions, TrayIcon
from ui.voice_dialogs import Toast, ask_confirm, ask_pick
from voice.controller import VoiceAssistant, VoiceUI

DEBOUNCE_SECOND = 2
VOICE_KEY_POLL_MS = 50
STATIC_HOTKEYS = ("ctrl+alt+s", "ctrl+alt+q", "ctrl+alt+p", "ctrl+alt+e", "ctrl+alt+i")


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
        self.voice_settings_window = None
        self.voice_hotkey_id = None
        self.mode_hotkey_ids = []
        self.modes = {}
        self.toast = None
        self.voice = VoiceAssistant(VoiceUI(
            ui_call=self.request_task,
            show=self.show_voice_message,
            confirm=lambda question: ask_confirm(self, question),
            pick=lambda heard, options: ask_pick(self, heard, options) if options else None,
            run_mode=self.voice_run_mode,
        ))
        self.voice_hotkey = ""          # set by register_voice_hotkey()

        self.protocol("WM_DELETE_WINDOW", self.stop_system)
        self.reload_modes()
        self.voice.start()
        self.register_static_hotkeys()
        self.tray = TrayIcon(TrayActions(
            mode_manager=lambda: self.request_task(self.open_config_ui, False),
            voice_settings=lambda: self.request_task(self.open_voice_settings),
            status=lambda: self.request_task(self.show_status_ui, "System state overview"),
            toggle_pause=lambda: self.request_task(self.toggle_paused),
            is_paused=lambda: self.runtime.system_paused,
            quit=lambda: self.request_task(self.stop_system),
        ))
        self.after(100, self.process_tasks)

    def run(self):
        write_log("System started")
        self.has_tray = self.tray.start()
        # Mode Manager opens by itself only on the very first start; voice works
        # without modes, so later starts go straight to the background.
        if not self.modes and not self._onboarded():
            self.after(50, lambda: self.open_config_ui(startup=True))
        else:
            self.after(500, self.announce_background)
        self.mainloop()

    @staticmethod
    def _onboarded():
        try:
            with database.connect() as conn:
                return database.get_setting(conn, "onboarded") == "1"
        except sqlite3.Error:
            return False

    @staticmethod
    def _mark_onboarded():
        try:
            with database.connect() as conn:
                database.set_setting(conn, "onboarded", "1")
        except sqlite3.Error:
            pass

    def announce_background(self):
        hints = ["AutoH is running in the background.",
                 "Tray icon (by the clock): settings and Quit" if getattr(self, "has_tray", False)
                 else "Ctrl+Alt+E settings · Ctrl+Alt+Q quit"]
        if self.voice_hotkey:
            hints.insert(1, f"Hold {self.voice_hotkey.title()} to talk.")
        self.show_voice_message("\n".join(hints), 6000)

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

    def reload_modes(self):
        config = load_config(default={"modes": {}}, exit_on_missing=False)
        self.modes = config.get("modes", {})
        self.register_mode_hotkeys()
        self.voice.reload(self.modes)

    # ------------------------------------------------------------ voice

    def show_voice_message(self, text, hide_after_ms=3500):
        if self.toast is None or not self.toast.winfo_exists():
            self.toast = Toast(self)
        self.toast.show(text, hide_after_ms)

    def voice_press(self):
        if self.runtime.system_paused:
            self.show_voice_message("ระบบหยุดชั่วคราว (Ctrl+Alt+P เพื่อเปิด)", 2500)
            return
        if self.voice.begin():
            self.after(VOICE_KEY_POLL_MS, self._poll_voice_key)

    def _poll_voice_key(self):
        """Key repeat makes the hotkey fire many times, so release is detected by polling."""
        if self.runtime.shutdown_requested:
            return
        try:
            held = keyboard.is_pressed(self.voice_hotkey)
        except Exception:
            held = False
        if held:
            self.after(VOICE_KEY_POLL_MS, self._poll_voice_key)
        else:
            self.voice.end()

    def voice_run_mode(self, mode_name):
        """`run_mode` from voice keeps the open-once rule of mode hotkeys."""
        if self.runtime.already_opened:
            raise RuntimeError("เปิด mode ไปแล้ว กด Ctrl+Alt+S เพื่อ reset ก่อน")
        if not self.runtime.system_active:
            raise RuntimeError("ระบบไม่พร้อม")
        self.launch_apps_mode(mode_name)

    def register_voice_hotkey(self):
        """(Re)register push-to-talk from settings; none when voice is disabled."""
        if self.voice_hotkey_id is not None:
            try:
                keyboard.remove_hotkey(self.voice_hotkey_id)
            except (KeyError, ValueError):
                pass
            self.voice_hotkey_id = None
        self.voice_hotkey = VoiceAssistant.hotkey() if VoiceAssistant.enabled() else ""
        if not self.voice_hotkey:
            return
        try:
            self.voice_hotkey_id = keyboard.add_hotkey(
                self.voice_hotkey, lambda: self.request_task(self.voice_press)
            )
        except ValueError as exc:
            write_log(f"Invalid voice hotkey '{self.voice_hotkey}': {exc}", "WARN")
            self.voice_hotkey = ""

    def open_voice_settings(self):
        from ui.voice_settings import VoiceSettingsHost, show_voice_settings
        from voice import app_index
        from voice.actions import SITES

        def targets(kind):
            if kind == "app":
                return list(self.voice.ctx.apps)
            if kind == "site":
                return list(SITES)
            return list(self.modes)

        def rescan():
            apps = app_index.refresh(self.modes)
            self.voice.reload(self.modes)
            write_log(f"Voice app index rescanned: {len(apps)} apps")
            return len(self.voice.ctx.apps)

        def on_settings_saved():
            self.register_voice_hotkey()
            write_log(f"Voice settings saved: enabled={VoiceAssistant.enabled()} hotkey={self.voice_hotkey}")

        host = VoiceSettingsHost(
            voice_status=lambda: self.voice.status,
            taken_hotkeys=lambda: set(STATIC_HOTKEYS) | {
                s.get("hotkey", "") for s in self.modes.values() if s.get("hotkey")
            },
            targets=targets,
            on_settings_saved=on_settings_saved,
            on_aliases_changed=lambda: self.voice.reload(self.modes),
            rescan_apps=rescan,
        )
        self.voice_settings_window = show_voice_settings(self, host, self.voice_settings_window)

    def register_static_hotkeys(self):
        keyboard.add_hotkey("ctrl+alt+s", lambda: self.request_task(self.start_system))
        keyboard.add_hotkey("ctrl+alt+q", lambda: self.request_task(self.stop_system))
        keyboard.add_hotkey("ctrl+alt+p", lambda: self.request_task(self.toggle_paused))
        keyboard.add_hotkey("ctrl+alt+e", lambda: self.request_task(self.open_config_ui, False))
        keyboard.add_hotkey(
            "ctrl+alt+i", lambda: self.request_task(self.show_status_ui, "System state overview")
        )
        self.register_voice_hotkey()

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
            start_time=self.runtime.start_time,
            system_active=self.runtime.system_active,
            system_paused=self.runtime.system_paused,
            already_opened=self.runtime.already_opened,
            modes=self.modes,
            voice=self.voice.status,
            voice_hotkey=self.voice_hotkey if self.voice.status == "ready" else "",
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
            on_open_voice=self.open_voice_settings,
            on_voice_imported=self.on_voice_imported,
        )

    def on_voice_imported(self):
        self.register_voice_hotkey()
        self.voice.reload(self.modes)

    def on_modes_changed(self, modes, message):
        self.modes = modes
        self.register_mode_hotkeys()
        self.voice.reload(modes)
        write_log(message)
        self.show_status_ui(message)

    def on_config_close(self, has_modes, startup):
        self.config_window = None
        self.reload_modes()

        if startup:
            # v1 quit here when no mode was saved. v2 keeps running: voice works
            # without modes, and closing a window must never stop the app.
            self._mark_onboarded()
            write_log(f"Setup window closed ({len(self.modes)} modes); running in background")
            self.announce_background()

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
        self.tray.refresh()

    def stop_system(self):
        if self.runtime.shutdown_requested:
            return

        self.runtime.shutdown_requested = True
        write_log("Shutdown requested")
        self.tray.stop()

        try:
            keyboard.unhook_all()
        except Exception as exc:
            write_log(f"Hotkey cleanup error: {exc}")

        if self.voice.recorder.is_recording:
            self.voice.recorder.stop()
        for window in (self.config_window, self.status_window, self.toast, self.voice_settings_window):
            if window is not None and window.winfo_exists():
                window.destroy()

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
