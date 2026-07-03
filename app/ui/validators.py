from __future__ import annotations

from dataclasses import dataclass

RESERVED_SYSTEM_HOTKEYS = {
    "ctrl+alt+s",
    "ctrl+alt+q",
    "ctrl+alt+p",
    "ctrl+alt+e",
    "ctrl+alt+i",
}


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    message: str = ""


def normalize_hotkey(raw_hotkey: str) -> str:
    return (raw_hotkey or "").strip().lower()


def normalize_mode_name(raw_mode_name: str) -> str:
    return (raw_mode_name or "").strip()


def normalize_urls(raw_urls: str) -> str:
    if not raw_urls:
        return ""

    parts = [part.strip() for part in raw_urls.split(",")]
    return ", ".join(part for part in parts if part)


def validate_mode_name(mode_name: str) -> ValidationResult:
    if not normalize_mode_name(mode_name):
        return ValidationResult(False, "Please enter a mode name.")
    return ValidationResult(True)


def validate_hotkey(hotkey: str, existing_hotkeys: set[str]) -> ValidationResult:
    normalized_hotkey = normalize_hotkey(hotkey)
    if not normalized_hotkey:
        return ValidationResult(False, "Please enter a hotkey.")

    if normalized_hotkey in RESERVED_SYSTEM_HOTKEYS:
        return ValidationResult(False, f"Hotkey {normalized_hotkey} is reserved by the system.")

    if normalized_hotkey in existing_hotkeys:
        return ValidationResult(False, f"Hotkey {normalized_hotkey} is already in use.")

    try:
        import keyboard

        keyboard.parse_hotkey(normalized_hotkey)
    except (ImportError, ValueError):
        return ValidationResult(
            False,
            f"Hotkey '{normalized_hotkey}' is invalid. Use real keys such as ctrl+alt+w.",
        )

    return ValidationResult(True)


def validate_mode_form(mode_name: str, hotkey: str, existing_hotkeys: set[str]) -> ValidationResult:
    mode_name_result = validate_mode_name(mode_name)
    if not mode_name_result.ok:
        return mode_name_result

    return validate_hotkey(hotkey, existing_hotkeys)


def build_mode_result(mode_name: str, hotkey: str, urls: str, apps: list[dict]) -> dict:
    return {
        "mode_name": normalize_mode_name(mode_name),
        "hotkey": normalize_hotkey(hotkey),
        "urls": normalize_urls(urls),
        "apps": apps,
    }
