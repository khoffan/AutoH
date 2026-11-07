"""Installed-app index for voice commands, cached in the app_index table.

Reuses the scanners the config window already uses (registry + Start Menu).
"""
from __future__ import annotations

import os
import sqlite3

from config import database


def scan_apps(modes: dict | None = None) -> list[tuple[str, str, str]]:
    """Scan the system. Returns [(name, path, source)] with existing paths only."""
    from system.normalize import normalize_apps
    from system.registry import get_apps_from_registry
    from system.start_menus import get_apps_from_start_menu

    found: dict[str, tuple[str, str, str]] = {}
    for app in normalize_apps(get_apps_from_registry(), get_apps_from_start_menu()):
        path = app.get("path") or app.get("exe") or ""
        if app.get("name") and path and os.path.exists(path):
            found[app["name"]] = (app["name"], path, app.get("source", "scan"))

    # Apps the user already picked for modes are trusted and win over scan results.
    for settings in (modes or {}).values():
        for name, path in settings.get("apps", {}).items():
            if path and os.path.exists(path):
                found[name] = (name, path, "mode")
    return list(found.values())


def refresh(modes: dict | None = None) -> dict[str, str]:
    apps = scan_apps(modes)
    try:
        with database.connect() as conn:
            database.write_app_index(conn, apps)
    except sqlite3.Error as exc:
        print(f"Cannot save app index: {exc}")
    return {name: path for name, path, _ in apps}


def load(modes: dict | None = None) -> dict[str, str]:
    """Cached index; scans on first use."""
    try:
        with database.connect() as conn:
            apps = database.read_app_index(conn)
    except sqlite3.Error:
        apps = {}
    return apps or refresh(modes)
