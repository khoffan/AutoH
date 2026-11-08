"""System tray icon: shows AutoH is running in the background and gives a menu.

pystray runs its own Windows message loop on a separate thread, so every menu
action is handed to the Tk thread through the callbacks (request_task).
If pystray/Pillow are missing the app still runs, just without a tray icon.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Callable

from core.logger import write_log

ICON_FILE = os.path.join("assets", "autoH_icon.ico")


@dataclass
class TrayActions:
    mode_manager: Callable[[], None]
    voice_settings: Callable[[], None]
    status: Callable[[], None]
    toggle_pause: Callable[[], None]
    is_paused: Callable[[], bool]
    quit: Callable[[], None]


def _icon_path() -> str:
    """assets/ next to the bundled code (PyInstaller) or at the project root (dev)."""
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    return os.path.join(base, ICON_FILE)


def _load_image():
    from PIL import Image, ImageDraw

    try:
        return Image.open(_icon_path())
    except OSError:
        # Fallback: dark rounded square with an "H"
        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((4, 4, 60, 60), radius=16, fill=(20, 20, 20, 255))
        draw.text((24, 18), "H", fill=(255, 255, 255, 255))
        return image


class TrayIcon:
    def __init__(self, actions: TrayActions):
        self.actions = actions
        self._icon = None

    def start(self) -> bool:
        try:
            import pystray
        except ImportError as exc:
            write_log(f"Tray icon unavailable: {exc}", "WARN")
            return False

        a = self.actions
        menu = pystray.Menu(
            pystray.MenuItem("AutoH is running", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Status", lambda: a.status(), default=True),  # left click
            pystray.MenuItem("Mode Manager", lambda: a.mode_manager()),
            pystray.MenuItem("Voice Settings", lambda: a.voice_settings()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Pause", lambda: a.toggle_pause(), checked=lambda _item: a.is_paused()),
            pystray.MenuItem("Quit AutoH", lambda: a.quit()),
        )
        try:
            self._icon = pystray.Icon("AutoH", _load_image(), "AutoH — running", menu)
            self._icon.run_detached()
        except Exception as exc:  # no tray on this desktop session, etc.
            write_log(f"Tray icon failed to start: {exc}", "WARN")
            self._icon = None
            return False
        write_log("Tray icon started")
        return True

    def refresh(self) -> None:
        """Re-evaluate the Pause checkmark after the state changed elsewhere."""
        if self._icon is not None:
            try:
                self._icon.update_menu()
            except Exception:
                pass

    def stop(self) -> None:
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass
            self._icon = None
