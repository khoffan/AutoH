"""Config API backed by SQLite (see config/database.py).

Function names and return shapes are unchanged from the JSON version, so
callers keep working: load_config() -> {"modes": {name: {hotkey, apps, urls?}}}.
"""
import copy
import json
import sqlite3

from config import database

DEFAULT_CONFIG = {"modes": {}}


def load_config(default=None, exit_on_missing=False):
    """Return {"modes": {...}}. Never raises; falls back to `default` on error.

    `exit_on_missing` is kept for backward compatibility and ignored.
    """
    try:
        with database.connect() as conn:
            modes = database.read_modes(conn)
    except sqlite3.Error as exc:
        print(f"Cannot read config: {exc}")
        return copy.deepcopy(DEFAULT_CONFIG if default is None else default)
    return {"modes": modes}


def save_modes(modes):
    """Replace all modes. Returns True on success."""
    try:
        normalized = database.normalize_modes({"modes": modes})
        with database.connect() as conn:
            database.write_modes(conn, normalized)
        return True
    except (ValueError, sqlite3.Error) as exc:
        print(f"Cannot save config: {exc}")
        return False


def save_config(config_data):
    return save_modes(config_data.get("modes", {}))


def save_config_file(mode_name, hotkey, app_list, urls=""):
    modes = load_config()["modes"]
    mode_data = {
        "hotkey": hotkey,
        "apps": {app["name"]: (app.get("path") or app.get("exe")) for app in app_list},
    }
    if urls:
        mode_data["urls"] = urls
    modes[mode_name] = mode_data
    return save_modes(modes)


def delete_mode(mode_name):
    modes = load_config()["modes"]
    modes.pop(mode_name, None)
    return save_modes(modes)


def export_config(file_path):
    """Write current modes to a JSON file. Raises OSError on failure."""
    data = load_config()
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def read_import_file(file_path):
    """Read and validate a JSON config file. Returns modes dict.

    Raises ValueError (bad content) or OSError (cannot read). Nothing is saved.
    """
    with open(file_path, "r", encoding="utf-8-sig") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Not valid JSON (line {exc.lineno}): {exc.msg}") from exc
    return database.normalize_modes(data)
