"""Text normalization and fuzzy name matching (Thai + English)."""
from __future__ import annotations

import re
from difflib import SequenceMatcher

# Polite/filler endings removed from the end of a command, longest first.
_TRAILING_FILLERS = sorted(
    ["ให้หน่อย", "หน่อย", "ด้วย", "ให้ที", "ครับ", "คับ", "ค่ะ", "คะ", "นะ", "จ้า", "please"],
    key=len,
    reverse=True,
)
# ASCII + common typographic punctuation only. Not [^\w\s]: Thai vowels/tone marks are not \w.
_PUNCT = re.compile(r"[!-/:-@\[-`{-~“”‘’…«»。、]")


def normalize(text: str) -> str:
    """Lowercase, drop punctuation, collapse spaces, strip trailing polite words."""
    text = _PUNCT.sub(" ", text.lower())
    text = re.sub(r"\s+", " ", text).strip()
    changed = True
    while changed and text:
        changed = False
        for filler in _TRAILING_FILLERS:
            if text.endswith(filler) and len(text) > len(filler):
                text = text[: -len(filler)].rstrip()
                changed = True
    return text


def _compact(text: str) -> str:
    return normalize(text).replace(" ", "")


def score(query: str, candidate: str) -> float:
    """0..1 similarity against the whole name or, scaled by 0.9, its best single word.

    "chrome" vs "Google Chrome" = 0.9 (word hit); "crome" = 0.82 (ask, not auto).
    """
    q, c = _compact(query), _compact(candidate)
    if not q or not c:
        return 0.0
    if q == c:
        return 1.0
    ratio = SequenceMatcher(None, q, c).ratio()
    words = normalize(candidate).split()
    if len(words) > 1:
        word_ratio = max(SequenceMatcher(None, q, w).ratio() for w in words)
        ratio = max(ratio, 0.9 * word_ratio)
    return ratio


def best_match(query: str, candidates) -> tuple[str | None, float]:
    """Return (best candidate, score) from an iterable of names."""
    best, best_score = None, 0.0
    for candidate in candidates:
        s = score(query, candidate)
        if s > best_score:
            best, best_score = candidate, s
    return best, best_score
