"""Voice Settings window: general (on/off, hotkey, rescan, system commands), aliases, history."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Callable

import customtkinter as ctk
from config import database
from ui.theme import APP_THEME, PADDING, fit_and_center_window
from voice import intents
from voice.actions import SYSTEM_ACTION_LABELS
from voice.controller import VoiceAssistant, validate_voice_hotkey

HISTORY_LIMIT = 100
_KIND_LABELS = {"app": "โปรแกรม", "site": "เว็บ", "mode": "โหมด"}
_RESULT_COLORS = {"done": "success", "cancelled": "warning", "rejected": "danger", "error": "danger"}


@dataclass
class VoiceSettingsHost:
    """What the window needs from the running app."""
    voice_status: Callable[[], str]
    taken_hotkeys: Callable[[], set]            # system + mode hotkeys (not the voice one)
    targets: Callable[[str], list]              # kind -> names for the alias target list
    on_settings_saved: Callable[[], None]       # re-register the voice hotkey
    on_aliases_changed: Callable[[], None]      # reload the voice context
    rescan_apps: Callable[[], int]              # rescan installed apps, return count


def _button(parent, text, command, kind="secondary", **kw):
    colors = {
        "primary": (APP_THEME["primary"], APP_THEME["primary_hover"], APP_THEME["primary_text"]),
        "danger": (APP_THEME["danger"], APP_THEME["danger_hover"], APP_THEME["danger_text"]),
        "secondary": (APP_THEME["surface_alt"], APP_THEME["panel_border"], APP_THEME["text"]),
    }[kind]
    return ctk.CTkButton(parent, text=text, command=command, fg_color=colors[0],
                         hover_color=colors[1], text_color=colors[2], **kw)


class VoiceSettingsWindow(ctk.CTkToplevel):
    def __init__(self, master, host: VoiceSettingsHost):
        super().__init__(master, fg_color=APP_THEME["window_bg"])
        self.host = host
        self.title("AutoH Voice Settings")
        fit_and_center_window(self, "760x640", min_size=(680, 560))
        self.transient(master)

        self.tabs = ctk.CTkTabview(self, fg_color=APP_THEME["surface"],
                                   segmented_button_selected_color=APP_THEME["primary"])
        self.tabs.pack(expand=True, fill="both", padx=PADDING["outer"], pady=PADDING["outer"])
        self._build_general(self.tabs.add("ทั่วไป"))
        self._build_aliases(self.tabs.add("คำที่จำไว้ (Alias)"))
        self._build_history(self.tabs.add("ประวัติคำสั่ง"))
        self.after(50, self.focus_window)

    def focus_window(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    # ------------------------------------------------------------ general

    def _build_general(self, tab):
        tab.grid_columnconfigure(1, weight=1)
        self.enabled_var = ctk.BooleanVar(value=VoiceAssistant.enabled())
        ctk.CTkSwitch(tab, text="เปิดใช้สั่งงานด้วยเสียง", variable=self.enabled_var,
                      text_color=APP_THEME["text"]).grid(row=0, column=0, columnspan=3, sticky="w",
                                                         padx=PADDING["panel"], pady=(PADDING["panel"], 8))

        ctk.CTkLabel(tab, text="ปุ่มกดค้างเพื่อพูด", text_color=APP_THEME["text"]).grid(
            row=1, column=0, sticky="w", padx=PADDING["panel"], pady=8)
        self.hotkey_entry = ctk.CTkEntry(tab, placeholder_text="ctrl+alt+v")
        self.hotkey_entry.insert(0, VoiceAssistant.hotkey())
        self.hotkey_entry.grid(row=1, column=1, sticky="ew", padx=(0, PADDING["panel"]), pady=8)

        _button(tab, "บันทึก", self.save_general, "primary", width=120).grid(
            row=1, column=2, padx=(0, PADDING["panel"]), pady=8)

        self.status_label = ctk.CTkLabel(tab, text="", justify="left", anchor="w",
                                         text_color=APP_THEME["text_muted"])
        self.status_label.grid(row=2, column=0, columnspan=3, sticky="ew", padx=PADDING["panel"], pady=8)

        ctk.CTkFrame(tab, height=1, fg_color=APP_THEME["panel_border"]).grid(
            row=3, column=0, columnspan=3, sticky="ew", padx=PADDING["panel"], pady=12)
        ctk.CTkLabel(tab, text="ติดตั้งโปรแกรมใหม่แล้วสั่งเปิดด้วยเสียงไม่เจอ? สแกนรายการโปรแกรมใหม่",
                     text_color=APP_THEME["text"]).grid(row=4, column=0, columnspan=2, sticky="w",
                                                        padx=PADDING["panel"])
        _button(tab, "สแกนโปรแกรมใหม่", self.rescan, width=160).grid(
            row=4, column=2, padx=(0, PADDING["panel"]))
        self._build_action_switches(tab, row=5)
        self._refresh_status()

    def _build_action_switches(self, tab, row):
        """System commands on/off (v2.1). Saved on every toggle; applies to the next command."""
        ctk.CTkFrame(tab, height=1, fg_color=APP_THEME["panel_border"]).grid(
            row=row, column=0, columnspan=3, sticky="ew", padx=PADDING["panel"], pady=12)
        ctk.CTkLabel(tab, text="คำสั่งระบบที่ใช้ได้ (ปิด = พูดแล้วไม่ทำ)", text_color=APP_THEME["text"],
                     font=ctk.CTkFont(weight="bold")).grid(
            row=row + 1, column=0, columnspan=3, sticky="w", padx=PADDING["panel"])
        box = ctk.CTkFrame(tab, fg_color="transparent")
        box.grid(row=row + 2, column=0, columnspan=3, sticky="ew", padx=PADDING["panel"], pady=(4, 0))
        box.grid_columnconfigure((0, 1), weight=1)

        disabled = self._read_disabled()
        self.action_vars = {}
        for n, (name, label) in enumerate(SYSTEM_ACTION_LABELS.items()):
            var = ctk.BooleanVar(value=name not in disabled)
            self.action_vars[name] = var
            ctk.CTkSwitch(box, text=label, variable=var, command=self.save_action_switches,
                          text_color=APP_THEME["text"]).grid(row=n // 2, column=n % 2, sticky="w", pady=4)

    @staticmethod
    def _read_disabled() -> set:
        try:
            with database.connect() as conn:
                return database.read_disabled_actions(conn)
        except sqlite3.Error:
            return set()

    def save_action_switches(self):
        off = [name for name, var in self.action_vars.items() if not var.get()]
        if not self._write(lambda conn: database.write_disabled_actions(conn, off)):
            return
        self._refresh_status("✓ บันทึกแล้ว" + (f" (ปิด: {', '.join(SYSTEM_ACTION_LABELS[n] for n in off)})"
                                               if off else " (เปิดทุกคำสั่ง)"))

    def _refresh_status(self, extra=""):
        text = f"สถานะ: {self.host.voice_status()}"
        self.status_label.configure(text=text + (f"\n{extra}" if extra else ""))

    def save_general(self):
        hotkey = self.hotkey_entry.get().strip().lower()
        error = validate_voice_hotkey(hotkey, self.host.taken_hotkeys())
        if error:
            self._refresh_status(f"✗ {error}")
            return
        if not VoiceAssistant.save_settings(self.enabled_var.get(), hotkey):
            self._refresh_status("✗ บันทึกลงฐานข้อมูลไม่ได้")
            return
        self.host.on_settings_saved()
        self._refresh_status(f"✓ บันทึกแล้ว ({'เปิด' if self.enabled_var.get() else 'ปิด'}, {hotkey})")

    def rescan(self):
        self._refresh_status("กำลังสแกน...")
        self.update_idletasks()
        count = self.host.rescan_apps()
        self._refresh_status(f"✓ พบ {count} โปรแกรม")
        self._refresh_target_values()

    # ------------------------------------------------------------ aliases

    def _build_aliases(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        form = ctk.CTkFrame(tab, fg_color="transparent")
        form.grid(row=0, column=0, sticky="ew", padx=PADDING["panel"], pady=(PADDING["panel"], 8))
        form.grid_columnconfigure((0, 2), weight=1)
        self.alias_entry = ctk.CTkEntry(form, placeholder_text="คำที่พูด เช่น ร้าย")
        self.alias_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.kind_var = ctk.StringVar(value="app")
        ctk.CTkOptionMenu(form, values=list(_KIND_LABELS), variable=self.kind_var, width=90,
                          command=lambda _v: self._refresh_target_values()).grid(row=0, column=1, padx=6)
        self.target_box = ctk.CTkComboBox(form, values=[])
        self.target_box.grid(row=0, column=2, sticky="ew", padx=6)
        _button(form, "เพิ่ม", self.add_alias, "primary", width=80).grid(row=0, column=3, padx=(6, 0))

        self.alias_list = ctk.CTkScrollableFrame(tab, fg_color=APP_THEME["surface_alt"])
        self.alias_list.grid(row=1, column=0, sticky="nsew", padx=PADDING["panel"], pady=(0, 8))
        self.alias_list.grid_columnconfigure(0, weight=1)

        bottom = ctk.CTkFrame(tab, fg_color="transparent")
        bottom.grid(row=2, column=0, sticky="ew", padx=PADDING["panel"], pady=(0, PADDING["panel"]))
        self.alias_feedback = ctk.CTkLabel(bottom, text="", text_color=APP_THEME["text_muted"])
        self.alias_feedback.pack(side="left")
        _button(bottom, "คืนค่าคำเริ่มต้น", self.restore_defaults, width=140).pack(side="right")

        self._refresh_target_values()
        self.render_aliases()

    def _refresh_target_values(self):
        values = sorted(self.host.targets(self.kind_var.get()), key=str.lower)
        self.target_box.configure(values=values)
        if self.target_box.get() not in values:
            self.target_box.set(values[0] if values else "")

    def _read_aliases(self) -> dict:
        try:
            with database.connect() as conn:
                return database.read_aliases(conn)
        except sqlite3.Error:
            return {}

    def render_aliases(self):
        for child in self.alias_list.winfo_children():
            child.destroy()
        aliases = self._read_aliases()
        learned = sorted(a for a in aliases if a not in database.DEFAULT_ALIASES)
        defaults = sorted(a for a in aliases if a in database.DEFAULT_ALIASES)
        for row, alias in enumerate(learned + defaults):
            target, kind = aliases[alias]
            tag = "" if alias in database.DEFAULT_ALIASES else "  • จำจากการใช้งาน"
            ctk.CTkLabel(self.alias_list, anchor="w", text_color=APP_THEME["text"],
                         text=f"\"{alias}\"  →  {target}  ({_KIND_LABELS.get(kind, kind)}){tag}").grid(
                row=row, column=0, sticky="ew", padx=8, pady=2)
            _button(self.alias_list, "ลบ", lambda a=alias: self.delete_alias(a), "danger",
                    width=56, height=26).grid(row=row, column=1, padx=8, pady=2)
        self.alias_feedback.configure(text=f"{len(learned)} คำที่จำจากการใช้งาน, {len(defaults)} คำเริ่มต้น")

    def add_alias(self):
        alias = self.alias_entry.get().strip().lower()
        target, kind = self.target_box.get().strip(), self.kind_var.get()
        if len(alias.replace(" ", "")) < 2 or not target:
            self.alias_feedback.configure(text="✗ ใส่คำที่พูด (อย่างน้อย 2 ตัวอักษร) และเลือกเป้าหมาย")
            return
        if target not in self.host.targets(kind):
            self.alias_feedback.configure(text=f"✗ ไม่รู้จัก \"{target}\" ในรายการ{_KIND_LABELS[kind]}")
            return
        self._write(lambda conn: database.write_alias(conn, alias, target, kind))
        self.alias_entry.delete(0, "end")
        self.render_aliases()
        self.alias_feedback.configure(text=f"✓ \"{alias}\" → {target}")

    def delete_alias(self, alias):
        self._write(lambda conn: database.delete_alias(conn, alias))
        self.render_aliases()
        self.alias_feedback.configure(text=f"✓ ลบ \"{alias}\" แล้ว")

    def restore_defaults(self):
        existing = self._read_aliases()
        missing = {a: v for a, v in database.DEFAULT_ALIASES.items() if a not in existing}
        self._write(lambda conn: [database.write_alias(conn, a, t, k) for a, (t, k) in missing.items()])
        self.render_aliases()
        self.alias_feedback.configure(text=f"✓ คืนค่า {len(missing)} คำ")

    def _write(self, func):
        try:
            with database.connect() as conn:
                func(conn)
        except sqlite3.Error as exc:
            self.alias_feedback.configure(text=f"✗ บันทึกไม่ได้: {exc}")
            return False
        self.host.on_aliases_changed()   # reloads the voice context (aliases, disabled actions)
        return True

    # ------------------------------------------------------------ history

    def _build_history(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        self.history_list = ctk.CTkScrollableFrame(tab, fg_color=APP_THEME["surface_alt"])
        self.history_list.grid(row=0, column=0, sticky="nsew", padx=PADDING["panel"], pady=PADDING["panel"])
        self.history_list.grid_columnconfigure(1, weight=1)
        _button(tab, "รีเฟรช", self.render_history, width=100).grid(
            row=1, column=0, sticky="e", padx=PADDING["panel"], pady=(0, PADDING["panel"]))
        self.render_history()

    def render_history(self):
        for child in self.history_list.winfo_children():
            child.destroy()
        try:
            with database.connect() as conn:
                rows = database.read_history(conn, HISTORY_LIMIT)
        except sqlite3.Error:
            rows = []
        if not rows:
            ctk.CTkLabel(self.history_list, text="ยังไม่มีประวัติ", text_color=APP_THEME["text_muted"]).grid(
                row=0, column=0, padx=8, pady=8)
        for row, (ts, heard, _source, actions, result) in enumerate(rows):
            names = ", ".join(a["name"] for a in json.loads(actions or "[]")) or "-"
            ctk.CTkLabel(self.history_list, text=ts[5:16], text_color=APP_THEME["text_muted"]).grid(
                row=row, column=0, sticky="w", padx=(8, 4), pady=2)
            ctk.CTkLabel(self.history_list, text=f"\"{heard}\"  →  {names}", anchor="w",
                         text_color=APP_THEME["text"]).grid(row=row, column=1, sticky="ew", padx=4, pady=2)
            ctk.CTkLabel(self.history_list, text=result,
                         text_color=APP_THEME[_RESULT_COLORS.get(result, "text_muted")]).grid(
                row=row, column=2, padx=4, pady=2)
            if result in ("rejected", "cancelled"):
                _button(self.history_list, "สร้าง alias", lambda h=heard: self.alias_from_history(h),
                        width=90, height=26).grid(row=row, column=3, padx=(4, 8), pady=2)

    def alias_from_history(self, heard: str):
        """Prefill the alias form with the name part of a failed command."""
        actions = intents.parse(heard)
        term = next((v for a in actions for k, v in a.args.items() if k in ("name", "site")), heard)
        self.alias_entry.delete(0, "end")
        self.alias_entry.insert(0, term)
        self.tabs.set("คำที่จำไว้ (Alias)")
        self.alias_feedback.configure(text=f"เลือกเป้าหมายของ \"{term}\" แล้วกดเพิ่ม")


def show_voice_settings(master, host: VoiceSettingsHost, existing=None):
    if existing is not None and existing.winfo_exists():
        existing.focus_window()
        return existing
    return VoiceSettingsWindow(master, host)
