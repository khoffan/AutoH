"""Rule-based intent parser (v2.0). Text in, list of Actions out (empty = not understood).

Returns a list so the LLM interpreter (v2.1) can plug in with the same shape.
"""
from __future__ import annotations

import re

from voice.actions import Action
from voice.matching import normalize

# Verb spellings include how Thai speech-to-text writes them: "open" -> โอเพ่น,
# "search" -> เสิร์ช, "ค้นหา" misheard as คนหา/ข้นหา.
_OPEN = r"เปิด|โอเพ่น|โอเพน|open|launch|start"
_SEARCH = r"ค้นหา|คนหา|ข้นหา|ค้น|หา|เสิร์ช|เซิร์ช|เซิร์ฟ|search(?: for)?|google"
_MODE = r"โหมด|โหมท|mode"

# Order matters: more specific prefixes first.
_RULES: list[tuple[re.Pattern, str, str]] = [
    (re.compile(rf"^(?:เข้า|{_OPEN}|ใช้)?\s*(?:{_MODE})\s*(.+)$"), "run_mode", "name"),
    (re.compile(rf"^(?:{_SEARCH})\s*(.+)$"), "web_search", "query"),
    (re.compile(rf"^(?:(?:{_OPEN})\s*(?:เว็บไซต์|เว็บ|website)|ไปที่เว็บ|ไปที่|go to)\s*(.+)$"),
     "open_url", "site"),
    (re.compile(rf"^(?:(?:{_OPEN})\s*(?:โปรแกรม|แอป|แอพ)?)\s*(.+)$"), "open_app", "name"),
]


def parse(text: str) -> list[Action]:
    cleaned = normalize(text)
    if not cleaned:
        return []
    for pattern, action_name, arg in _RULES:
        match = pattern.match(cleaned)
        if match and match.group(1).strip():
            return [Action(action_name, {arg: match.group(1).strip()})]
    return []
