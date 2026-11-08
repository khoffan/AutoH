"""Microsoft Store / packaged apps (Notepad, Calculator, Paint, ... on Windows 11).

They are not in the registry uninstall keys or the Start Menu folders, so the
other scanners never see them. Windows lists them in its Applications folder;
`Get-StartApps` reads that list. A packaged app is opened through
shell:AppsFolder\\<AppUserModelID>, which is what the Start menu does too.
"""
from __future__ import annotations

import json
import subprocess

APPS_FOLDER = "shell:AppsFolder\\"
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def is_packaged_path(path: str) -> bool:
    return (path or "").lower().startswith(APPS_FOLDER.lower())


def package_family(path: str) -> str:
    """'shell:AppsFolder\\Microsoft.WindowsNotepad_8wekyb3d8bbwe!App' -> 'Microsoft.WindowsNotepad_8wekyb3d8bbwe'."""
    return path[len(APPS_FOLDER):].split("!", 1)[0] if is_packaged_path(path) else ""


def get_store_apps(timeout: float = 15.0) -> list[dict]:
    """[{"name", "path", "source": "store"}] for packaged apps; [] if unavailable."""
    command = ["powershell", "-NoProfile", "-NonInteractive", "-Command",
               "[Console]::OutputEncoding = [Text.Encoding]::UTF8; "
               "Get-StartApps | ConvertTo-Json -Compress"]
    try:
        result = subprocess.run(command, capture_output=True, timeout=timeout,
                                creationflags=_NO_WINDOW)
        items = json.loads(result.stdout.decode("utf-8", "replace") or "[]")
    except (OSError, subprocess.SubprocessError, ValueError):
        return []
    if isinstance(items, dict):
        items = [items]
    apps = []
    for item in items:
        name, app_id = (item.get("Name") or "").strip(), (item.get("AppID") or "").strip()
        if name and "!" in app_id:          # "!" = packaged app; desktop apps come from the other scanners
            apps.append({"name": name, "path": APPS_FOLDER + app_id, "source": "store"})
    return apps
