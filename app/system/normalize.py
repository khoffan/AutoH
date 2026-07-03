import os
import re

STRICT_INSTALLER_WORDS = {
    "installer",
    "setup",
    "uninstall",
    "uninst",
    "patcher",
    "updater",
    "bootstrapper",
}

PROGRAMMING_TOOL_WORDS = {
    "python",
    "pip",
    "node",
    "npm",
    "npx",
    "git",
    "mingw",
    "msys",
    "gcc",
    "g++",
    "cmake",
    "jdk",
    "jre",
    "sdk",
    "anaconda",
    "miniconda",
    "rustup",
    "cargo",
    "go tool",
    "visual studio build tools",
}

SYSTEM_BACKGROUND_WORDS = {
    "service",
    "services",
    "runtime",
    "redistributable",
    "telemetry",
    "update health",
    "edgewebview",
    "webview2",
    "host",
    "driver",
    "framework",
    "x64",
    "x86",
}

OFFICE_ALLOW_WORDS = {
    "office",
    "microsoft 365",
    "word",
    "excel",
    "powerpoint",
    "outlook",
    "onenote",
    "access",
    "publisher",
    "teams",
}

BROWSER_ALLOW_WORDS = {
    "edge",
    "chrome",
    "firefox",
    "brave",
    "opera",
    "vivaldi",
    "browser",
}

BROWSER_BLOCK_WORDS = {
    "webview",
    "webview2",
    "edgewebview",
    "runtime",
    "service",
}

ALLOWED_TOOL_NAMES = set()
EXECUTABLE_EXTENSIONS = (".exe", ".lnk", ".bat", ".cmd")
EXECUTABLE_PATTERN = "|".join(ext.lstrip(".") for ext in EXECUTABLE_EXTENSIONS)


def _extract_path(raw_path):
    if not raw_path:
        return ""

    raw = raw_path.strip()
    if not raw:
        return ""

    cleaned = re.sub(r",[-\d]+$", "", raw).strip().strip('"')

    if raw.startswith('"'):
        quoted_match = re.match(r'^"([^"]+)"', raw)
        if quoted_match:
            cleaned = quoted_match.group(1).strip()

    if not os.path.splitext(cleaned)[1]:
        ext_match = re.search(rf"(?i)^(.+?\.({EXECUTABLE_PATTERN}))\b", raw)
        if ext_match:
            cleaned = ext_match.group(1).strip().strip('"')

    return cleaned


def _canonicalize_path(raw_path):
    extracted = _extract_path(raw_path)
    if not extracted:
        return ""

    normalized = os.path.expandvars(extracted)
    normalized = os.path.expanduser(normalized)
    normalized = os.path.normpath(normalized)
    return os.path.realpath(normalized)


def _get_app_path(app):
    return _canonicalize_path(app.get("path") or app.get("exe") or "")


def _has_valid_path(app):
    candidate = _get_app_path(app)
    return bool(candidate and os.path.exists(candidate))


def _is_installer(name, path):
    searchable = " ".join(
        [
            name.lower(),
            os.path.basename(path).lower() if path else "",
        ]
    )
    return any(word in searchable for word in STRICT_INSTALLER_WORDS)


def _is_programming_tool(name, path):
    if name.lower() in ALLOWED_TOOL_NAMES:
        return False

    searchable = " ".join(
        [
            name.lower(),
            os.path.basename(path).lower() if path else "",
            path.lower() if path else "",
        ]
    )
    return any(word in searchable for word in PROGRAMMING_TOOL_WORDS)


def _is_irrelevant_system_entry(name, path):
    searchable = " ".join(
        [
            name.lower(),
            os.path.basename(path).lower() if path else "",
            path.lower() if path else "",
        ]
    )

    is_microsoft_or_windows = (
        "microsoft" in searchable or "windows" in searchable or "ms " in searchable
    )
    if not is_microsoft_or_windows:
        return False

    # Keep only Office family when entry looks Microsoft/Windows related.
    if any(word in searchable for word in OFFICE_ALLOW_WORDS):
        return False

    # Non-Office Microsoft/Windows entries are removed from UI list.
    return True


def _is_background_service_entry(name, path):
    searchable = " ".join(
        [
            name.lower(),
            os.path.basename(path).lower() if path else "",
            path.lower() if path else "",
        ]
    )
    return any(word in searchable for word in SYSTEM_BACKGROUND_WORDS)


def _is_browser_app(name, path):
    searchable = " ".join(
        [
            name.lower(),
            os.path.basename(path).lower() if path else "",
            path.lower() if path else "",
        ]
    )
    if any(word in searchable for word in BROWSER_BLOCK_WORDS):
        return False
    return any(word in searchable for word in BROWSER_ALLOW_WORDS)


def _build_merge_key(name):
    key = name.lower()
    key = re.sub(r"\b\d+(\.\d+)*\b", "", key)
    key = re.sub(r"[()\[\]{}]", " ", key)
    key = re.sub(r"\s+", " ", key).strip()
    return key


def _candidate_score(app):
    path = _get_app_path(app)
    score = 0

    if path and os.path.exists(path):
        score += 100

    if path.lower().endswith(".exe"):
        score += 30
    elif path.lower().endswith(".lnk"):
        score += 20

    if app.get("source") == "registry":
        score += 10
    elif app.get("source") == "start_menu":
        score += 5

    return score


def normalize_apps(reg_apps, menu_apps):
    app_dict = {}

    print(f"Normalizing apps: {len(reg_apps)} from registry, {len(menu_apps)} from start menu")

    for app in menu_apps + reg_apps:
        name = app.get("name", "").strip()
        if not name:
            continue

        raw_path = app.get("path") or app.get("exe") or ""
        canonical_path = _canonicalize_path(raw_path)

        if _is_installer(name, canonical_path):
            print(f"--> [Filtered Out] Installer/Uninstaller detected: {name} ({raw_path})")
            continue

        if _is_programming_tool(name, canonical_path):
            print(f"--> [Filtered Out] Programming tool detected: {name} ({raw_path})")
            continue

        is_browser = _is_browser_app(name, canonical_path)

        if not is_browser and _is_background_service_entry(name, canonical_path):
            print(f"--> [Filtered Out] Background/service entry detected: {name} ({raw_path})")
            continue

        if not is_browser and _is_irrelevant_system_entry(name, canonical_path):
            print(
                f"--> [Filtered Out] Non-Office Microsoft/Windows entry detected: {name} ({raw_path})"
            )
            continue

        candidate = app.copy()
        if candidate.get("path"):
            candidate["path"] = canonical_path or candidate["path"]
        elif candidate.get("exe"):
            candidate["exe"] = canonical_path or candidate["exe"]

        key = _build_merge_key(name)
        if key not in app_dict:
            app_dict[key] = candidate
            continue

        existing_app = app_dict[key]
        if _candidate_score(candidate) > _candidate_score(existing_app):
            merged = candidate.copy()
            for field, value in existing_app.items():
                if value and not merged.get(field):
                    merged[field] = value
            app_dict[key] = merged
            continue

        if not _has_valid_path(existing_app) and _has_valid_path(candidate):
            existing_app.update(candidate)
            continue

        for field, value in candidate.items():
            if value and not existing_app.get(field):
                existing_app[field] = value

    return sorted(app_dict.values(), key=lambda item: item.get("name", "").lower())
