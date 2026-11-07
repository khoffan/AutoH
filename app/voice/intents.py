"""Rule-based intent parser (v2.0). Text in, list of Actions out (empty = not understood).

Returns a list so the LLM interpreter (v2.1) can plug in with the same shape.
"""
from __future__ import annotations

import re

from voice.actions import Action
from voice.matching import normalize

# Order matters: more specific prefixes first.
_RULES: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"^(?:เข้า|เปิด|ใช้)?\s*(?:โหมด|mode)\s*(.+)$"), "run_mode", "name"),
    (re.compile(r"^(?:ค้นหา|ค้น|หา|search(?: for)?|google)\s*(.+)$"), "web_search", "query"),
    (re.compile(r"^(?:เปิดเว็บไซต์|เปิดเว็บ|ไปที่เว็บ|ไปที่|open website|go to)\s*(.+)$"),
     "open_url", "site"),
    (re.compile(r"^(?:เปิดโปรแกรม|เปิดแอป|เปิดแอพ|เปิด|open|launch|start)\s*(.+)$"),
     "open_app", "name"),
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
