"""Small windows for voice commands: toast, yes/no confirm, pick-from-list.

Confirm and pick block (wait_window) on the Tk thread and always end: no answer
before the timeout counts as "no" / "none", so nothing runs without the user.
"""
from __future__ import annotations

import customtkinter as ctk
from ui.theme import APP_THEME

CONFIRM_TIMEOUT_S = 8
PICK_TIMEOUT_S = 15
_MARGIN = 24


def _place_bottom_right(window, width, height):
    window.update_idletasks()
    x = window.winfo_screenwidth() - width - _MARGIN
    y = window.winfo_screenheight() - height - _MARGIN * 3
    window.geometry(f"{width}x{height}+{x}+{y}")


class Toast(ctk.CTkToplevel):
    """Bottom-right status line ("กำลังฟัง...", result). Reused between commands."""

    def __init__(self, master):
        super().__init__(master, fg_color=APP_THEME["surface"])
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self._label = ctk.CTkLabel(self, text="", wraplength=340, justify="left",
                                   font=ctk.CTkFont(size=14), text_color=APP_THEME["text"])
        self._label.pack(expand=True, fill="both", padx=16, pady=12)
        self._hide_job = None
        _place_bottom_right(self, 380, 72)
        self.withdraw()

    def show(self, text: str, hide_after_ms: int | None = 3500):
        if self._hide_job is not None:
            self.after_cancel(self._hide_job)
            self._hide_job = None
        self._label.configure(text=text)
        self.deiconify()
        self.lift()
        if hide_after_ms:
            self._hide_job = self.after(hide_after_ms, self.withdraw)


class _Dialog(ctk.CTkToplevel):
    def __init__(self, master, title: str, timeout_s: int, height: int):
        super().__init__(master, fg_color=APP_THEME["surface"])
        self.title(title)
        self.attributes("-topmost", True)
        self.resizable(False, False)
        self.result = None
        self._remaining = timeout_s
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.bind("<Escape>", lambda _e: self.cancel())
        _place_bottom_right(self, 400, height)
        self._timer = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=12),
                                   text_color=APP_THEME["text_muted"])

    def _tick(self):
        if self._remaining <= 0:
            self.cancel()
            return
        self._timer.configure(text=f"ยกเลิกอัตโนมัติใน {self._remaining} วินาที (Esc)")
        self._remaining -= 1
        self.after(1000, self._tick)

    def run(self):
        self._timer.pack(side="bottom", pady=(0, 10))
        self._tick()
        self.lift()
        self.focus_force()
        self.grab_set()
        self.wait_window()
        return self.result

    def choose(self, value):
        self.result = value
        self.destroy()

    def cancel(self):
        self.result = None
        self.destroy()


def ask_confirm(master, question: str, timeout_s: int = CONFIRM_TIMEOUT_S) -> bool:
    dialog = _Dialog(master, "AutoH", timeout_s, height=150)
    ctk.CTkLabel(dialog, text=question, wraplength=360, font=ctk.CTkFont(size=15, weight="bold"),
                 text_color=APP_THEME["text"]).pack(padx=16, pady=(16, 10))
    row = ctk.CTkFrame(dialog, fg_color="transparent")
    row.pack(fill="x", padx=16)
    ctk.CTkButton(row, text="ใช่ (Enter)", command=lambda: dialog.choose(True),
                  fg_color=APP_THEME["primary"], hover_color=APP_THEME["primary_hover"]
                  ).pack(side="left", expand=True, fill="x", padx=(0, 6))
    ctk.CTkButton(row, text="ไม่ใช่", command=dialog.cancel, fg_color=APP_THEME["surface_alt"],
                  text_color=APP_THEME["text"], hover_color=APP_THEME["panel_border"]
                  ).pack(side="left", expand=True, fill="x", padx=(6, 0))
    dialog.bind("<Return>", lambda _e: dialog.choose(True))
    return dialog.run() is True


def ask_pick(master, heard: str, options: list[tuple[str, str, float]],
             timeout_s: int = PICK_TIMEOUT_S) -> tuple[str, str] | None:
    """options: [(kind, name, score)]. Returns (kind, name) or None."""
    dialog = _Dialog(master, "AutoH", timeout_s, height=110 + 44 * len(options))
    ctk.CTkLabel(dialog, text=f"ไม่พบ \"{heard}\" — หมายถึงอันไหน?", wraplength=360,
                 font=ctk.CTkFont(size=15, weight="bold"), text_color=APP_THEME["text"]
                 ).pack(padx=16, pady=(16, 8))
    labels = {"app": "โปรแกรม", "site": "เว็บ", "mode": "โหมด"}
    fallbacks = {"web_search": "🔎 ค้นหา \"{}\" ใน Google", "play_music": "▶ เล่น \"{}\" บน YouTube"}
    for n, (kind, name, _score) in enumerate(options, 1):
        text = (f"{n}. " + fallbacks[kind].format(name)) if kind in fallbacks \
            else f"{n}. {name}  ({labels.get(kind, kind)})"
        ctk.CTkButton(dialog, text=text, anchor="w",
                      command=lambda k=kind, v=name: dialog.choose((k, v)),
                      fg_color=APP_THEME["surface_alt"], text_color=APP_THEME["text"],
                      hover_color=APP_THEME["selection"]).pack(fill="x", padx=16, pady=3)
        dialog.bind(str(n), lambda _e, k=kind, v=name: dialog.choose((k, v)))
    return dialog.run()
