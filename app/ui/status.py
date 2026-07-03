from __future__ import annotations

import time
from dataclasses import dataclass

import customtkinter as ctk
from ui.theme import APP_THEME, PADDING, WINDOW_SIZES, fit_and_center_window


@dataclass
class StatusSnapshot:
    runtime: int
    start_time: float
    system_active: bool
    system_paused: bool
    already_opened: bool
    modes: dict[str, dict]


class StatusWindow(ctk.CTkToplevel):
    def __init__(self, master, snapshot: StatusSnapshot, message=""):
        super().__init__(master, fg_color=APP_THEME["window_bg"])
        self.title("AutoH Status")
        fit_and_center_window(self, WINDOW_SIZES["status"], min_size=(520, 640))
        self.resizable(False, False)
        self.attributes("-topmost", True)

        container = ctk.CTkFrame(
            self,
            fg_color=APP_THEME["surface"],
            corner_radius=14,
            border_width=1,
            border_color=APP_THEME["panel_border"],
        )
        container.pack(expand=True, fill="both", padx=PADDING["outer"], pady=PADDING["outer"])
        container.grid_rowconfigure(1, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.message_label = ctk.CTkLabel(
            container,
            text=message or "System state overview",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=APP_THEME["text"],
        )
        self.message_label.grid(
            row=0,
            column=0,
            sticky="w",
            padx=PADDING["panel"],
            pady=(PADDING["panel"], 8),
        )

        content_frame = ctk.CTkScrollableFrame(
            container,
            fg_color=APP_THEME["surface_alt"],
            corner_radius=10,
            border_width=1,
            border_color=APP_THEME["panel_border"],
            label_text="Runtime Details",
            label_fg_color=APP_THEME["surface_alt"],
            label_text_color=APP_THEME["text"],
        )
        content_frame.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=PADDING["panel"],
            pady=(0, PADDING["panel"]),
        )
        content_frame.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(
            content_frame,
            text="",
            justify="left",
            anchor="w",
            font=ctk.CTkFont(size=13),
            text_color=APP_THEME["text"],
        )
        self.status_label.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=PADDING["panel"],
            pady=(PADDING["panel"], 10),
        )

        self.hotkeys_label = ctk.CTkLabel(
            content_frame,
            text="",
            justify="left",
            anchor="w",
            font=ctk.CTkFont(size=12),
            text_color=APP_THEME["text_muted"],
        )
        self.hotkeys_label.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=PADDING["panel"],
            pady=(0, PADDING["panel"]),
        )

        ctk.CTkButton(
            container,
            text="Close",
            command=self.destroy,
            fg_color=APP_THEME["primary"],
            hover_color=APP_THEME["primary_hover"],
            text_color=APP_THEME["primary_text"],
            height=40,
        ).grid(
            row=2,
            column=0,
            sticky="ew",
            padx=PADDING["panel"],
            pady=(0, PADDING["panel"]),
        )

        self.update_snapshot(snapshot, message)

    def update_snapshot(self, snapshot: StatusSnapshot, message=""):
        remaining = max(0, int(snapshot.runtime - (time.time() - snapshot.start_time)))
        minutes, seconds = divmod(remaining, 60)
        status_text = (
            f"Active: {snapshot.system_active}\n"
            f"Paused: {snapshot.system_paused}\n"
            f"Opened: {snapshot.already_opened}\n"
            f"Time Left: {minutes} min {seconds} sec\n"
            f"Saved Modes: {len(snapshot.modes)}"
        )
        hotkeys = [
            f"{name}: {settings.get('hotkey', '-')}"
            for name, settings in sorted(snapshot.modes.items())
        ]
        hotkeys_text = "System Hotkeys:\nCtrl+Alt+S reset\nCtrl+Alt+P pause\nCtrl+Alt+Q shutdown\nCtrl+Alt+E configure\nCtrl+Alt+I status"
        if hotkeys:
            hotkeys_text += "\n\nMode Hotkeys:\n" + "\n".join(hotkeys)

        self.message_label.configure(text=message or "System state overview")
        self.status_label.configure(text=status_text)
        self.hotkeys_label.configure(text=hotkeys_text)


def show_status_window(master, snapshot: StatusSnapshot, existing_window=None, message=""):
    if existing_window is not None and existing_window.winfo_exists():
        existing_window.update_snapshot(snapshot, message)
        existing_window.focus_force()
        existing_window.lift()
        return existing_window
    return StatusWindow(master, snapshot=snapshot, message=message)
