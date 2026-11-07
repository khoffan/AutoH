"""Action registry shared by the rule parser (v2.0) and the LLM interpreter (v2.1).

Every action the app can perform is declared here once. Nothing outside this
registry can be executed from voice input.
"""
from __future__ import annotations

import webbrowser
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable
from urllib.parse import quote_plus


class Risk(str, Enum):
    SAFE = "safe"            # run without asking (if the name match is confident)
    CONFIRM = "confirm"      # always ask first
    CRITICAL = "critical"    # ask first + cancellable countdown (v2.1)


@dataclass
class Action:
    name: str
    args: dict = field(default_factory=dict)
    confidence: float = 1.0   # < 1.0 when the verb itself was guessed (fuzzy), see intents


@dataclass
class ActionContext:
    """Everything handlers and the resolver may use. Side effects are injectable for tests."""

    apps: dict[str, str]                       # app name -> path (app_index)
    modes: dict[str, dict]                     # from load_config()["modes"]
    aliases: dict[str, tuple[str, str]]        # spoken alias -> (target, kind)
    sites: dict[str, str] = field(default_factory=lambda: dict(SITES))
    open_app: Callable[[str, str], None] | None = None   # (path, name)
    open_url: Callable[[str], None] = webbrowser.open
    run_mode: Callable[[str], None] | None = None
    open_path: Callable[[str], None] | None = None   # folders and ms-settings: URIs; os.startfile


def _startfile(target: str) -> None:
    import os

    os.startfile(target)


@dataclass(frozen=True)
class ActionSpec:
    name: str
    description: str
    params: dict                     # JSON-schema "properties"
    required: tuple[str, ...]
    risk: Risk
    handler: Callable[[dict, ActionContext], str]


SITES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "facebook": "https://www.facebook.com",
    "github": "https://github.com",
    "chatgpt": "https://chatgpt.com",
    "claude": "https://claude.ai",
}

YOUTUBE_SEARCH = "https://www.youtube.com/results?search_query="

# Spoken folder name -> Windows known folder. Paths come from the shell API
# (handles OneDrive redirection), never from what was said.
FOLDERS = {
    "desktop": "Desktop", "เดสก์ท็อป": "Desktop", "เดสท็อป": "Desktop",
    "documents": "Documents", "เอกสาร": "Documents",
    "downloads": "Downloads", "ดาวน์โหลด": "Downloads",
    "pictures": "Pictures", "รูปภาพ": "Pictures", "รูป": "Pictures",
    "music": "Music", "เพลง": "Music",
    "videos": "Videos", "วิดีโอ": "Videos", "วีดีโอ": "Videos",
}
_KNOWN_FOLDER_IDS = {
    "Desktop": "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}",
    "Documents": "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}",
    "Downloads": "{374DE290-123F-4565-9164-39C4925E467B}",
    "Pictures": "{33E28130-4E1E-4676-835A-98395C3BC3BB}",
    "Music": "{4BD8D571-6D19-48D3-BE97-422220080E43}",
    "Videos": "{18989B1D-99B5-455B-841C-AB7C74E4DDFC}",
}

# Spoken settings page -> fixed ms-settings: URI (whitelist).
SETTINGS = {
    "home": "ms-settings:", "หน้าหลัก": "ms-settings:",
    "wifi": "ms-settings:network-wifi", "ไวไฟ": "ms-settings:network-wifi",
    "network": "ms-settings:network-status", "เครือข่าย": "ms-settings:network-status",
    "อินเทอร์เน็ต": "ms-settings:network-status", "เน็ต": "ms-settings:network-status",
    "bluetooth": "ms-settings:bluetooth", "บลูทูธ": "ms-settings:bluetooth",
    "sound": "ms-settings:sound", "เสียง": "ms-settings:sound",
    "display": "ms-settings:display", "หน้าจอ": "ms-settings:display", "จอ": "ms-settings:display",
    "battery": "ms-settings:batterysaver", "แบตเตอรี่": "ms-settings:batterysaver",
    "แบต": "ms-settings:batterysaver",
    "update": "ms-settings:windowsupdate", "อัปเดต": "ms-settings:windowsupdate",
    "อัพเดท": "ms-settings:windowsupdate", "อัพเดต": "ms-settings:windowsupdate",
    "apps": "ms-settings:appsfeatures", "แอป": "ms-settings:appsfeatures",
    "แอพ": "ms-settings:appsfeatures",
    "microphone": "ms-settings:privacy-microphone", "ไมโครโฟน": "ms-settings:privacy-microphone",
    "ไมค์": "ms-settings:privacy-microphone",
    "mouse": "ms-settings:mousetouchpad", "เมาส์": "ms-settings:mousetouchpad",
    "keyboard": "ms-settings:keyboard", "คีย์บอร์ด": "ms-settings:keyboard",
    "language": "ms-settings:regionlanguage", "ภาษา": "ms-settings:regionlanguage",
}


def known_folder_path(folder: str) -> str:
    """Real path of a Windows known folder ("Downloads"), with a home-dir fallback."""
    import os

    try:
        import ctypes
        import uuid
        from ctypes import wintypes

        guid = uuid.UUID(_KNOWN_FOLDER_IDS[folder])
        buf = ctypes.c_wchar_p()
        hr = ctypes.windll.shell32.SHGetKnownFolderPath(
            ctypes.byref((ctypes.c_byte * 16).from_buffer_copy(guid.bytes_le)), 0, None, ctypes.byref(buf)
        )
        if hr == 0 and buf.value:
            path = buf.value
            ctypes.windll.ole32.CoTaskMemFree(buf)
            return path
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), folder)

REGISTRY: dict[str, ActionSpec] = {}


def register(spec: ActionSpec) -> None:
    REGISTRY[spec.name] = spec


def tool_definitions() -> list[dict]:
    """Registry as LLM tool definitions (v2.1)."""
    return [
        {
            "name": spec.name,
            "description": spec.description,
            "input_schema": {
                "type": "object",
                "properties": spec.params,
                "required": list(spec.required),
            },
        }
        for spec in REGISTRY.values()
    ]


# ---------------------------------------------------------------- handlers
# Handlers receive args already resolved by validate.resolve() (canonical names, real paths).

def _open_app(args: dict, ctx: ActionContext) -> str:
    if ctx.open_app is None:
        # Like clicking the icon: focus if running, launch if not (modes use safe_open_app).
        from core.launcher import open_or_focus

        how = open_or_focus(args["path"], args["name"])
        return f"{how} app {args['name']}"
    ctx.open_app(args["path"], args["name"])
    return f"opened app {args['name']}"


def _open_url(args: dict, ctx: ActionContext) -> str:
    ctx.open_url(args["url"])
    return f"opened {args['url']}"


def _web_search(args: dict, ctx: ActionContext) -> str:
    ctx.open_url("https://www.google.com/search?q=" + quote_plus(args["query"]))
    return f"searched {args['query']}"


def _run_mode(args: dict, ctx: ActionContext) -> str:
    if ctx.run_mode is None:
        raise RuntimeError("run_mode is not available")
    ctx.run_mode(args["name"])
    return f"ran mode {args['name']}"


_NAME = {"name": {"type": "string", "description": "Name as the user said it."}}

register(ActionSpec(
    "open_app", "Open an installed program by name.", _NAME, ("name",), Risk.SAFE, _open_app,
))
register(ActionSpec(
    "open_url", "Open a known website by name (e.g. youtube, gmail).",
    {"site": {"type": "string", "description": "Website name."}}, ("site",), Risk.SAFE, _open_url,
))
register(ActionSpec(
    "web_search", "Search the web in the default browser.",
    {"query": {"type": "string", "description": "Search text."}}, ("query",), Risk.SAFE, _web_search,
))
register(ActionSpec(
    "run_mode", "Run a saved AutoH mode (opens its apps and URLs).", _NAME, ("name",), Risk.SAFE,
    _run_mode,
))


def _play_music(args: dict, ctx: ActionContext) -> str:
    ctx.open_url(YOUTUBE_SEARCH + quote_plus(args["query"]))
    return f"played {args['query']} on YouTube"


def _open_folder(args: dict, ctx: ActionContext) -> str:
    (ctx.open_path or _startfile)(args["path"])
    return f"opened folder {args['name']}"


def _open_settings(args: dict, ctx: ActionContext) -> str:
    (ctx.open_path or _startfile)(args["uri"])
    return f"opened settings {args['page']}"


register(ActionSpec(
    "play_music", "Play a song or artist (searches YouTube).",
    {"query": {"type": "string", "description": "Song, artist or genre."}}, ("query",), Risk.SAFE,
    _play_music,
))
register(ActionSpec(
    "open_folder", "Open a standard folder: desktop, documents, downloads, pictures, music, videos.",
    _NAME, ("name",), Risk.SAFE, _open_folder,
))
register(ActionSpec(
    "open_settings", "Open a Windows Settings page (wifi, bluetooth, sound, display, ...).",
    {"page": {"type": "string", "description": "Settings page name."}}, ("page",), Risk.SAFE,
    _open_settings,
))
