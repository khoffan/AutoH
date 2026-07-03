from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk
from config.load_config import load_config, save_modes
from system.normalize import normalize_apps
from system.registry import get_apps_from_registry
from system.start_menus import get_apps_from_start_menu
from ui.theme import APP_THEME, PADDING, WINDOW_SIZES, fit_and_center_window
from ui.validators import build_mode_result, normalize_mode_name, validate_mode_form


def configure_customtkinter():
    ctk.set_appearance_mode(APP_THEME["appearance_mode"])
    ctk.set_default_color_theme("blue")


class ConfigWindow(ctk.CTkToplevel):
    HOTKEY_PREFIX = "ctrl+alt+"

    def __init__(self, master, on_modes_changed=None, on_close=None, startup=False):
        super().__init__(master, fg_color=APP_THEME["window_bg"])
        self.on_modes_changed = on_modes_changed
        self.on_close_callback = on_close
        self.startup = startup
        self.all_apps = normalize_apps(get_apps_from_registry(), get_apps_from_start_menu())
        self.current_modes = load_config(default={"modes": {}}, exit_on_missing=False).get(
            "modes", {}
        )
        self.filtered_apps = list(self.all_apps)
        self.selected_apps = []
        self.selected_source_keys = set()
        self.editing_mode_name = None
        self.feedback_var = tk.StringVar(value="Create a mode or edit an existing one.")

        self.title("AutoH Mode Manager")
        fit_and_center_window(self, WINDOW_SIZES["config"], min_size=(1120, 720))
        self.protocol("WM_DELETE_WINDOW", self.handle_close)
        self.transient(master)

        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=3)
        self.grid_columnconfigure(2, weight=3)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_modes_panel()
        self._build_source_panel()
        self._build_editor_panel()

        self.render_mode_list()
        self.render_source_list()
        self.render_selected_apps()

        self.after(50, self.focus_window)

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(
            row=0,
            column=0,
            columnspan=3,
            sticky="ew",
            padx=PADDING["outer"],
            pady=(PADDING["outer"], PADDING["section"]),
        )
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="AutoH Mode Manager",
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color=APP_THEME["text"],
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            header,
            text="Light mode only, plain colors, clear contrast, and faster mode management.",
            font=ctk.CTkFont(size=13),
            text_color=APP_THEME["text_muted"],
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        self.feedback_label = ctk.CTkLabel(
            header,
            textvariable=self.feedback_var,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=APP_THEME["text_muted"],
        )
        self.feedback_label.grid(row=2, column=0, sticky="w", pady=(10, 0))

    def _build_modes_panel(self):
        panel = self._panel_frame("Saved Modes")
        panel.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=(PADDING["outer"], PADDING["section"]),
            pady=(0, PADDING["outer"]),
        )
        panel.grid_rowconfigure(2, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            panel,
            text="New Mode",
            command=self.reset_form,
            fg_color=APP_THEME["primary"],
            hover_color=APP_THEME["primary_hover"],
            text_color=APP_THEME["primary_text"],
            height=42,
        ).grid(
            row=0,
            column=0,
            sticky="ew",
            padx=PADDING["panel"],
            pady=(PADDING["panel"], PADDING["control"]),
        )

        ctk.CTkLabel(
            panel,
            text="Edit, rename, or delete saved modes from here.",
            font=ctk.CTkFont(size=12),
            text_color=APP_THEME["text_muted"],
        ).grid(row=1, column=0, sticky="w", padx=PADDING["panel"], pady=(0, PADDING["control"]))

        self.modes_frame = ctk.CTkScrollableFrame(
            panel,
            fg_color=APP_THEME["surface_alt"],
            corner_radius=10,
            border_width=1,
            border_color=APP_THEME["panel_border"],
            label_text="Configured Modes",
            label_fg_color=APP_THEME["surface_alt"],
            label_text_color=APP_THEME["text"],
        )
        self.modes_frame.grid(
            row=2, column=0, sticky="nsew", padx=PADDING["panel"], pady=(0, PADDING["panel"])
        )
        self.modes_frame.grid_columnconfigure(0, weight=1)

    def _build_source_panel(self):
        panel = self._panel_frame("Discover Apps")
        panel.grid(
            row=1, column=1, sticky="nsew", padx=(0, PADDING["section"]), pady=(0, PADDING["outer"])
        )
        panel.grid_rowconfigure(3, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(panel, text="Search installed apps", text_color=APP_THEME["text"]).grid(
            row=0, column=0, sticky="w", padx=PADDING["panel"], pady=(PADDING["panel"], 6)
        )

        self.search_entry = ctk.CTkEntry(
            panel,
            placeholder_text="Type to filter apps",
            fg_color=APP_THEME["input_bg"],
            border_color=APP_THEME["input_border"],
            text_color=APP_THEME["text"],
            height=40,
        )
        self.search_entry.grid(row=1, column=0, sticky="ew", padx=PADDING["panel"])
        self.search_entry.bind("<KeyRelease>", self.on_search_change)

        ctk.CTkLabel(
            panel,
            text="Select multiple apps, then move them into the mode editor.",
            font=ctk.CTkFont(size=12),
            text_color=APP_THEME["text_muted"],
        ).grid(row=2, column=0, sticky="w", padx=PADDING["panel"], pady=(8, PADDING["control"]))

        self.source_frame = ctk.CTkScrollableFrame(
            panel,
            fg_color=APP_THEME["surface_alt"],
            corner_radius=10,
            border_width=1,
            border_color=APP_THEME["panel_border"],
            label_text="Available Apps",
            label_fg_color=APP_THEME["surface_alt"],
            label_text_color=APP_THEME["text"],
        )
        self.source_frame.grid(row=3, column=0, sticky="nsew", padx=PADDING["panel"])
        self.source_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            panel,
            text="Add Selected Apps",
            command=self.add_selected_apps,
            fg_color=APP_THEME["accent"],
            hover_color=APP_THEME["accent_hover"],
            text_color=APP_THEME["primary_text"],
            height=44,
        ).grid(row=4, column=0, sticky="ew", padx=PADDING["panel"], pady=PADDING["panel"])

    def _build_editor_panel(self):
        panel = self._panel_frame("Mode Editor")
        panel.grid(
            row=1, column=2, sticky="nsew", padx=(0, PADDING["outer"]), pady=(0, PADDING["outer"])
        )
        panel.grid_rowconfigure(6, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        self.mode_title_label = ctk.CTkLabel(
            panel,
            text="Create or update a mode",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=APP_THEME["text"],
        )
        self.mode_title_label.grid(
            row=0, column=0, sticky="w", padx=PADDING["panel"], pady=(PADDING["panel"], 8)
        )

        self.mode_name_entry = self._labeled_entry(panel, 1, "Mode name", "Work")
        self.hotkey_entry = self._labeled_entry(panel, 2, "Hotkey", "ctrl+alt+w")
        self._init_hotkey_entry_behavior()
        self.urls_entry = self._labeled_entry(
            panel, 3, "URLs", "https://mail.google.com, https://github.com"
        )

        ctk.CTkLabel(
            panel,
            text="Selected apps for this mode",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=APP_THEME["text"],
        ).grid(row=4, column=0, sticky="w", padx=PADDING["panel"], pady=(10, PADDING["control"]))

        self.selected_frame = ctk.CTkScrollableFrame(
            panel,
            fg_color=APP_THEME["surface_alt"],
            corner_radius=10,
            border_width=1,
            border_color=APP_THEME["panel_border"],
            height=240,
            label_text="Included Apps",
            label_fg_color=APP_THEME["surface_alt"],
            label_text_color=APP_THEME["text"],
        )
        self.selected_frame.grid(
            row=6, column=0, sticky="nsew", padx=PADDING["panel"], pady=(0, PADDING["panel"])
        )
        self.selected_frame.grid_columnconfigure(0, weight=1)

        actions = ctk.CTkFrame(panel, fg_color="transparent")
        actions.grid(
            row=7, column=0, sticky="ew", padx=PADDING["panel"], pady=(0, PADDING["panel"])
        )
        actions.grid_columnconfigure(0, weight=1)
        actions.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            actions,
            text="Save Mode",
            command=self.save_current_mode,
            fg_color=APP_THEME["primary"],
            hover_color=APP_THEME["primary_hover"],
            text_color=APP_THEME["primary_text"],
            height=46,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

        ctk.CTkButton(
            actions,
            text="Delete Mode",
            command=self.delete_current_mode,
            fg_color=APP_THEME["danger"],
            hover_color=APP_THEME["danger_hover"],
            text_color=APP_THEME["danger_text"],
            height=46,
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

    def _panel_frame(self, title):
        frame = ctk.CTkFrame(
            self,
            fg_color=APP_THEME["surface"],
            corner_radius=14,
            border_width=1,
            border_color=APP_THEME["panel_border"],
        )
        ctk.CTkLabel(
            frame,
            text=title,
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=APP_THEME["text"],
        ).grid(row=0, column=0, sticky="w", padx=PADDING["panel"], pady=(PADDING["panel"], 4))
        return frame

    def _labeled_entry(self, panel, row, label_text, placeholder_text):
        ctk.CTkLabel(panel, text=label_text, text_color=APP_THEME["text"]).grid(
            row=row, column=0, sticky="w", padx=PADDING["panel"], pady=(4, 6)
        )

        entry = ctk.CTkEntry(
            panel,
            placeholder_text=placeholder_text,
            fg_color=APP_THEME["input_bg"],
            border_color=APP_THEME["input_border"],
            text_color=APP_THEME["text"],
            height=40,
        )
        entry.grid(row=row, column=0, sticky="ew", padx=PADDING["panel"], pady=(28, 0))
        return entry

    def focus_window(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def set_feedback(self, message, color=None):
        self.feedback_var.set(message)
        self.feedback_label.configure(text_color=color or APP_THEME["text_muted"])

    def handle_close(self):
        if self.on_close_callback:
            self.on_close_callback(bool(self.current_modes))
        self.destroy()

    def on_search_change(self, _event=None):
        keyword = self.search_entry.get().strip().lower()
        if keyword:
            self.filtered_apps = [app for app in self.all_apps if keyword in app["name"].lower()]
        else:
            self.filtered_apps = list(self.all_apps)
        self.selected_source_keys.clear()
        self.render_source_list()

    def render_mode_list(self):
        for child in self.modes_frame.winfo_children():
            child.destroy()

        if not self.current_modes:
            ctk.CTkLabel(
                self.modes_frame,
                text="No saved modes yet.",
                text_color=APP_THEME["text_muted"],
            ).grid(row=0, column=0, sticky="w", padx=10, pady=10)
            return

        for row_index, mode_name in enumerate(sorted(self.current_modes)):
            settings = self.current_modes[mode_name]
            row = ctk.CTkFrame(
                self.modes_frame,
                fg_color=APP_THEME["surface"],
                corner_radius=10,
                border_width=1,
                border_color=APP_THEME["panel_border"],
            )
            row.grid(row=row_index, column=0, sticky="ew", padx=6, pady=6)
            row.grid_columnconfigure(0, weight=1)

            summary = f"{mode_name}\n{settings.get('hotkey', 'No hotkey')}"
            ctk.CTkButton(
                row,
                text=summary,
                anchor="w",
                command=lambda name=mode_name: self.load_mode(name),
                fg_color=APP_THEME["surface"],
                hover_color=APP_THEME["selection"],
                text_color=APP_THEME["text"],
                height=56,
            ).grid(row=0, column=0, sticky="ew", padx=(8, 6), pady=8)

            ctk.CTkButton(
                row,
                text="Delete",
                width=70,
                command=lambda name=mode_name: self.delete_mode(name),
                fg_color=APP_THEME["danger"],
                hover_color=APP_THEME["danger_hover"],
                text_color=APP_THEME["danger_text"],
            ).grid(row=0, column=1, padx=(0, 8), pady=8)

    def render_source_list(self):
        for child in self.source_frame.winfo_children():
            child.destroy()

        if not self.filtered_apps:
            ctk.CTkLabel(
                self.source_frame,
                text="No apps match the current search.",
                text_color=APP_THEME["text_muted"],
            ).grid(row=0, column=0, sticky="w", padx=10, pady=10)
            return

        for row_index, app in enumerate(self.filtered_apps):
            app_key = self._app_key(app)
            variable = tk.BooleanVar(value=app_key in self.selected_source_keys)

            row = ctk.CTkFrame(
                self.source_frame,
                fg_color=APP_THEME["surface"],
                corner_radius=8,
                border_width=1,
                border_color=APP_THEME["panel_border"],
            )
            row.grid(row=row_index, column=0, sticky="ew", padx=6, pady=4)
            row.grid_columnconfigure(1, weight=1)

            ctk.CTkCheckBox(
                row,
                text="",
                variable=variable,
                command=lambda key=app_key, var=variable: self.toggle_source(key, var.get()),
                fg_color=APP_THEME["primary"],
                hover_color=APP_THEME["primary_hover"],
                border_color=APP_THEME["input_border"],
            ).grid(row=0, column=0, padx=(10, 8), pady=10)

            ctk.CTkLabel(
                row,
                text=app["name"],
                anchor="w",
                text_color=APP_THEME["text"],
            ).grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=10)

    def render_selected_apps(self):
        for child in self.selected_frame.winfo_children():
            child.destroy()

        if not self.selected_apps:
            ctk.CTkLabel(
                self.selected_frame,
                text="Add apps from the middle panel, or leave it empty and use URLs only.",
                wraplength=320,
                justify="left",
                text_color=APP_THEME["text_muted"],
            ).grid(row=0, column=0, sticky="w", padx=10, pady=10)
            return

        for row_index, app in enumerate(self.selected_apps):
            row = ctk.CTkFrame(
                self.selected_frame,
                fg_color=APP_THEME["surface"],
                corner_radius=8,
                border_width=1,
                border_color=APP_THEME["panel_border"],
            )
            row.grid(row=row_index, column=0, sticky="ew", padx=6, pady=4)
            row.grid_columnconfigure(0, weight=1)

            app_path = app.get("path") or app.get("exe") or ""
            app_text = app["name"] if not app_path else f"{app['name']}\n{app_path}"
            ctk.CTkLabel(
                row,
                text=app_text,
                anchor="w",
                justify="left",
                text_color=APP_THEME["text"],
            ).grid(row=0, column=0, sticky="ew", padx=(10, 8), pady=10)

            ctk.CTkButton(
                row,
                text="Remove",
                width=76,
                command=lambda key=self._app_key(app): self.remove_selected_app(key),
                fg_color=APP_THEME["danger"],
                hover_color=APP_THEME["danger_hover"],
                text_color=APP_THEME["danger_text"],
            ).grid(row=0, column=1, padx=(0, 10), pady=10)

    def toggle_source(self, app_key, value):
        if value:
            self.selected_source_keys.add(app_key)
        else:
            self.selected_source_keys.discard(app_key)

    def add_selected_apps(self):
        if not self.selected_source_keys:
            self.set_feedback("Select at least one app before adding it.", APP_THEME["warning"])
            return

        existing_keys = {self._app_key(app) for app in self.selected_apps}
        for app in self.filtered_apps:
            app_key = self._app_key(app)
            if app_key in self.selected_source_keys and app_key not in existing_keys:
                self.selected_apps.append(app)

        self.selected_source_keys.clear()
        self.render_source_list()
        self.render_selected_apps()
        self.set_feedback("Selected apps added to the mode.", APP_THEME["success"])

    def remove_selected_app(self, app_key):
        self.selected_apps = [app for app in self.selected_apps if self._app_key(app) != app_key]
        self.render_selected_apps()

    def reset_form(self):
        self.editing_mode_name = None
        self.mode_title_label.configure(text="Create or update a mode")
        self._set_entry(self.mode_name_entry, "")
        self._set_hotkey_value("")
        self._set_entry(self.urls_entry, "")
        self.selected_apps = []
        self.render_selected_apps()
        self.set_feedback("Ready to create a new mode.")

    def load_mode(self, mode_name):
        settings = self.current_modes.get(mode_name, {})
        self.editing_mode_name = mode_name
        self.mode_title_label.configure(text=f"Editing: {mode_name}")
        self._set_entry(self.mode_name_entry, mode_name)
        self._set_hotkey_value(settings.get("hotkey", ""))
        self._set_entry(self.urls_entry, settings.get("urls", ""))
        self.selected_apps = self._resolve_saved_apps(settings.get("apps", {}))
        self.render_selected_apps()
        self.set_feedback(f"Loaded mode {mode_name}.")

    def save_current_mode(self):
        self._enforce_hotkey_prefix()
        mode_name = normalize_mode_name(self.mode_name_entry.get())
        hotkey = self.hotkey_entry.get()
        urls = self.urls_entry.get()

        if mode_name in self.current_modes and mode_name != self.editing_mode_name:
            self.set_feedback(
                f"Mode name {mode_name} already exists. Choose a different name.",
                APP_THEME["danger"],
            )
            return

        existing_hotkeys = {
            settings.get("hotkey", "")
            for name, settings in self.current_modes.items()
            if name != self.editing_mode_name
        }
        validation = validate_mode_form(mode_name, hotkey, existing_hotkeys)
        if not validation.ok:
            self.set_feedback(validation.message, APP_THEME["danger"])
            return

        if not self.selected_apps and not urls.strip():
            self.set_feedback(
                "Add at least one app or one URL to make the mode useful.", APP_THEME["danger"]
            )
            return

        result = build_mode_result(mode_name, hotkey, urls, self.selected_apps)
        mode_payload = {
            "hotkey": result["hotkey"],
            "apps": {app["name"]: (app.get("path") or app.get("exe")) for app in result["apps"]},
        }
        if result["urls"]:
            mode_payload["urls"] = result["urls"]

        if self.editing_mode_name and self.editing_mode_name != mode_name:
            self.current_modes.pop(self.editing_mode_name, None)

        self.current_modes[mode_name] = mode_payload
        save_modes(self.current_modes)
        self.editing_mode_name = mode_name
        self.mode_title_label.configure(text=f"Editing: {mode_name}")
        self.render_mode_list()
        self.set_feedback(f"Saved mode {mode_name}.", APP_THEME["success"])

        if self.on_modes_changed:
            self.on_modes_changed(dict(self.current_modes), f"Saved mode {mode_name}.")

    def delete_current_mode(self):
        if not self.editing_mode_name:
            self.set_feedback("Select a saved mode before deleting it.", APP_THEME["warning"])
            return
        self.delete_mode(self.editing_mode_name)

    def delete_mode(self, mode_name):
        if mode_name not in self.current_modes:
            return

        confirmed = messagebox.askyesno(
            "Delete mode",
            f"Delete mode '{mode_name}'? This only removes the saved configuration.",
            parent=self,
        )
        if not confirmed:
            return

        self.current_modes.pop(mode_name, None)
        save_modes(self.current_modes)

        if self.editing_mode_name == mode_name:
            self.reset_form()

        self.render_mode_list()
        self.set_feedback(f"Deleted mode {mode_name}.", APP_THEME["success"])

        if self.on_modes_changed:
            self.on_modes_changed(dict(self.current_modes), f"Deleted mode {mode_name}.")

    def _resolve_saved_apps(self, saved_apps):
        resolved = []
        for app_name, app_path in saved_apps.items():
            match = next(
                (
                    app
                    for app in self.all_apps
                    if app.get("name") == app_name
                    and (app.get("path") or app.get("exe")) == app_path
                ),
                None,
            )
            if match is not None:
                resolved.append(match)
            else:
                resolved.append({"name": app_name, "path": app_path})
        return resolved

    def _app_key(self, app):
        return app.get("name"), app.get("path") or app.get("exe") or ""

    def _set_entry(self, entry, value):
        entry.delete(0, "end")
        if value:
            entry.insert(0, value)

    def _init_hotkey_entry_behavior(self):
        self._set_hotkey_value("")
        self.hotkey_entry.bind("<KeyRelease>", self._enforce_hotkey_prefix)
        self.hotkey_entry.bind("<ButtonRelease-1>", self._enforce_hotkey_prefix)
        self.hotkey_entry.bind("<FocusIn>", self._enforce_hotkey_prefix)
        self.hotkey_entry.bind("<KeyPress>", self._prevent_prefix_delete)

    def _set_hotkey_value(self, raw_value):
        normalized = self._normalize_hotkey_text(raw_value)
        self._set_entry(self.hotkey_entry, normalized)
        self.hotkey_entry.icursor(len(normalized))

    def _normalize_hotkey_text(self, raw_text):
        normalized = (raw_text or "").strip().lower().replace(" ", "")

        if normalized.startswith(self.HOTKEY_PREFIX):
            suffix_raw = normalized[len(self.HOTKEY_PREFIX) :]
        else:
            suffix_raw = normalized.replace(self.HOTKEY_PREFIX, "")

        letters_only = [char for char in suffix_raw if char.isalpha()]
        suffix = letters_only[0] if letters_only else ""
        return f"{self.HOTKEY_PREFIX}{suffix}"

    def _enforce_hotkey_prefix(self, _event=None):
        current_text = self.hotkey_entry.get()
        normalized = self._normalize_hotkey_text(current_text)
        if current_text != normalized:
            self._set_entry(self.hotkey_entry, normalized)

        cursor_index = self.hotkey_entry.index("insert")
        min_cursor = len(self.HOTKEY_PREFIX)
        if cursor_index < min_cursor:
            self.hotkey_entry.icursor(min_cursor)

    def _prevent_prefix_delete(self, event):
        min_cursor = len(self.HOTKEY_PREFIX)
        cursor_index = self.hotkey_entry.index("insert")

        if event.keysym in {"BackSpace", "Left", "Home"} and cursor_index <= min_cursor:
            return "break"

        if event.keysym == "Delete" and cursor_index < min_cursor:
            return "break"

        return None


def show_configuration_window(master, on_modes_changed=None, on_close=None, startup=False):
    configure_customtkinter()
    return ConfigWindow(
        master, on_modes_changed=on_modes_changed, on_close=on_close, startup=startup
    )
