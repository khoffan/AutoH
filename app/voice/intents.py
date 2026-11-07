"""Rule-based intent parser (v2.0). Text in, list of Actions out (empty = not understood).

Returns a list so the LLM interpreter (v2.1) can plug in with the same shape.

Two passes:
1. Exact verb prefixes (regex). Confidence 1.0.
2. Fuzzy verb: the first syllables sound like a known verb ("คุณหา" ~ "ค้นหา").
   Confidence = verb_score; below AUTO threshold the user is asked first.
"""
from __future__ import annotations

import re

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
    (re.compile(rf"^(?:{_SEARCH})\s*(.+)$"), "web_search", "query"),
    (re.compile(rf"^(?:(?:{_OPEN})\s*(?:เว็บไซต์|เว็บ|website)|ไปที่เว็บ|ไปที่|go to)\s*(.+)$"),
     "open_url", "site"),
    (re.compile(rf"^(?:(?:{_OPEN})\s*(?:โปรแกรม|แอป|แอพ)?)\s*(.+)$"), "open_app", "name"),
]

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
    for pattern, action_name, arg in _RULES:
        match = pattern.match(cleaned)
        if match and match.group(1).strip():
            return [Action(action_name, {arg: match.group(1).strip()})]
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
