"""Rule-based intent parser (v2.0). Text in, list of Actions out (empty = not understood).

Returns a list so the LLM interpreter (v2.1) can plug in with the same shape.

Two passes:
1. Exact verb prefixes (regex). Confidence 1.0.
2. Fuzzy verb: the first syllables sound like a known verb ("คุณหา" ~ "ค้นหา").
   Confidence = verb_score; below AUTO threshold the user is asked first.
"""
from __future__ import annotations

import re
from typing import Callable

from voice.actions import Action
from voice.matching import normalize, verb_score

# Thai spellings of English verbs ("open" -> โอเพ่น, "search" -> เสิร์ช) cannot be
# caught by sound matching against Thai verbs, so they are listed here.
_OPEN = r"เปิด|โอเพ่น|โอเพน|open|launch|start"
_SEARCH = r"ค้นหา|ค้น|หา|เสิร์ช|เซิร์ช|เซิร์ฟ|search(?: for)?|google"
_MODE = r"โหมด|mode"

# Order matters: more specific prefixes first.
_RULES: list[tuple[re.Pattern, str, str]] = [
    (re.compile(rf"^(?:เข้า|{_OPEN}|ใช้)?\s*(?:{_MODE})\s*(.+)$"), "run_mode", "name"),
    (re.compile(rf"^(?:{_OPEN}|ไปที่)?\s*(?:การตั้งค่า|ตั้งค่า|settings?)\s*(.*)$"), "open_settings", "page"),
    (re.compile(rf"^(?:{_OPEN}|เล่น|ฟัง)\s*(?:เพลง|music|song)\s*(.+)$"), "play_music", "query"),
    (re.compile(r"^play\s+(?:music\s+|song\s+)?(.+)$"), "play_music", "query"),
    (re.compile(rf"^(?:{_OPEN})\s*(?:โฟลเดอร์|โฟลเดอ|แฟ้ม|folder)\s*(.+)$"), "open_folder", "name"),
    (re.compile(rf"^(?:{_SEARCH})\s*(.+)$"), "web_search", "query"),
    (re.compile(rf"^(?:(?:{_OPEN})\s*(?:เว็บไซต์|เว็บ|website)|ไปที่เว็บ|ไปที่|go to)\s*(.+)$"),
     "open_url", "site"),
    (re.compile(rf"^(?:(?:{_OPEN})\s*(?:โปรแกรม|แอป|แอพ)?)\s*(.+)$"), "open_app", "name"),
]

# ---------------------------------------------------------------- system commands (v2.1)
# Checked before _RULES: "ปิดเสียง" is mute, not "close the app called เสียง".

_THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
_NUMBER_WORDS = {
    "ศูนย์": 0, "หนึ่ง": 1, "เอ็ด": 1, "สอง": 2, "ยี่": 2, "สาม": 3, "สี่": 4, "ห้า": 5,
    "หก": 6, "เจ็ด": 7, "แปด": 8, "เก้า": 9, "สิบ": 10, "ร้อย": 100,
}
_NUMBER_TOKEN = re.compile("|".join(sorted(_NUMBER_WORDS, key=len, reverse=True)))
_PERCENT = re.compile(r"\s*(?:เปอร์เซ็นต์|เปอร์เซนต์|เปอร์เซ็น|เปอร์เซน|percent|%)$")


def parse_number(text: str) -> int | None:
    """'30', '๓๐', 'สามสิบ', 'ยี่สิบห้า', 'ร้อย', '50 เปอร์เซ็นต์' -> int. None if not a number."""
    text = _PERCENT.sub("", text.translate(_THAI_DIGITS).strip()).replace(" ", "")
    if not text:
        return None
    if text.isdigit():
        return int(text)
    total, digit, pos = 0, None, 0
    while pos < len(text):
        match = _NUMBER_TOKEN.match(text, pos)
        if not match:
            return None
        value = _NUMBER_WORDS[match.group()]
        if value in (10, 100):
            total += (1 if digit is None else digit) * value
            digit = None
        else:
            if digit is not None:
                return None           # two digits in a row ("สองสาม") is not a number
            digit = value
        pos = match.end()
    return total + (digit or 0)


_DEVICE = r"(?:\s*(?:เครื่อง|คอมพิวเตอร์|คอม|หน้าจอ|จอ|ลำโพง|ทั้งหมด|computer|pc|screen|now))?"
_UP = r"เพิ่มเสียง|เร่งเสียง|เสียงดังขึ้น|ดังขึ้น|volume up|turn up(?: the)? volume|louder"
_DOWN = r"ลดเสียง|เบาเสียง|เสียงเบาลง|เบาลง|volume down|turn down(?: the)? volume|quieter"


def _volume_level(match: re.Match) -> Action | None:
    level = parse_number(match.group(1))
    return Action("set_volume", {"level": level}) if level is not None and level <= 100 else None


def _volume_delta(sign: int):
    def build(match: re.Match) -> Action | None:
        amount = parse_number(match.group(1)) if match.group(1) else 10
        if amount is None or not 0 < amount <= 100:
            return None
        return Action("set_volume", {"delta": sign * amount})
    return build


_SYSTEM_RULES: list[tuple[re.Pattern, Callable[[re.Match], Action | None]]] = [
    (re.compile(rf"^(?:ปิดเสียง|มิวท์|มิวต์|mute|เงียบ){_DEVICE}$"), lambda m: Action("mute", {"on": True})),
    (re.compile(rf"^(?:{_UP})\s*(?:อีก)?\s*(.*?)$"), _volume_delta(+1)),
    (re.compile(rf"^(?:{_DOWN})\s*(?:อีก|ลง)?\s*(.*?)$"), _volume_delta(-1)),
    (re.compile(r"^(?:ตั้ง|ปรับ|เปิด|set)?\s*(?:ระดับ)?\s*(?:เสียง|volume)\s*(?:เป็น|ที่|ไว้ที่|to)?\s*(.+)$"),
     _volume_level),
    (re.compile(rf"^(?:เปิดเสียง|อันมิวท์|unmute|ยกเลิกปิดเสียง){_DEVICE}$"), lambda m: Action("mute", {"on": False})),
    (re.compile(rf"^(?:ล็อก|ล็อค|ล๊อก|ล๊อค|lock){_DEVICE}$"), lambda m: Action("lock_screen")),
    (re.compile(rf"^(?:sleep|สลีป|พักเครื่อง|พักคอม){_DEVICE}(?:\s*(?:mode|โหมด))?$"), lambda m: Action("sleep")),
    (re.compile(rf"^(?:ปิดเครื่อง|ปิดคอมพิวเตอร์|ปิดคอม|ปิดระบบ|shut ?down|ชัตดาวน์|ชัทดาวน์){_DEVICE}$"),
     lambda m: Action("shutdown")),
    (re.compile(rf"^(?:รีสตาร์ท|รีสตาร์ต|restart|reboot|รีบูต|รีบูท|เริ่มเครื่องใหม่|เริ่มระบบใหม่){_DEVICE}$"),
     lambda m: Action("restart")),
    (re.compile(r"^(?:ปิด|close|quit|exit|ออกจาก)\s*(?:โปรแกรม|แอป|แอพ|app)?\s*(.+)$"),
     lambda m: Action("close_app", {"name": m.group(1).strip()})),
]


def _parse_system(cleaned: str) -> list[Action] | None:
    for pattern, build in _SYSTEM_RULES:
        match = pattern.match(cleaned)
        if match:
            action = build(match)
            if action is not None:
                return [action]
    return None


# Canonical Thai verbs for the fuzzy pass, most specific first.
_FUZZY_VERBS: list[tuple[str, str, str]] = [
    ("เปิดเว็บ", "open_url", "site"),
    ("เข้าโหมด", "run_mode", "name"),
    ("โหมด", "run_mode", "name"),
    ("ค้นหา", "web_search", "query"),
    ("เปิด", "open_app", "name"),
]
FUZZY_VERB_MIN = 0.8
# Thai marks that attach to the previous letter; a word cannot be split before them.
_COMBINING = re.compile(r"[ัิ-ฺ็-๎]")


def parse(text: str) -> list[Action]:
    cleaned = normalize(text)
    if not cleaned:
        return []
    system = _parse_system(cleaned)
    if system:
        return system
    for pattern, action_name, arg in _RULES:
        match = pattern.match(cleaned)
        if not match:
            continue
        value = match.group(1).strip()
        if not value and action_name == "open_settings":
            value = "home"                      # "เปิดตั้งค่า" alone -> Settings home
        if value:
            return [Action(action_name, {arg: value})]
    return _parse_fuzzy_verb(cleaned)


def _parse_fuzzy_verb(cleaned: str) -> list[Action]:
    best: tuple[float, str, str, str] | None = None   # (score, action, arg, rest)
    for verb, action_name, arg in _FUZZY_VERBS:
        for cut in range(max(1, len(verb) - 2), min(len(cleaned), len(verb) + 3)):
            if _COMBINING.match(cleaned[cut]):
                continue
            head, rest = cleaned[:cut].strip(), cleaned[cut:].strip()
            if not head or not rest:
                continue
            s = verb_score(head, verb)
            if best is None or s > best[0]:
                best = (s, action_name, arg, rest)
    if best is None or best[0] < FUZZY_VERB_MIN:
        return []
    s, action_name, arg, rest = best
    return [Action(action_name, {arg: rest}, confidence=round(s, 2))]
