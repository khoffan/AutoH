"""Text normalization and fuzzy name matching (Thai + English)."""
from __future__ import annotations

import re
from difflib import SequenceMatcher

# Polite/filler endings removed from the end of a command, longest first.
_TRAILING_FILLERS = sorted(
    ["ให้หน่อย", "หน่อย", "ด้วย", "ให้ที", "ให้", "ครับ", "คับ", "ค่ะ", "คะ", "นะ", "น่ะ", "จ้า",
     "please"],
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


# Version numbers and "(64-bit)" / "(current user)" are never spoken.
_NAME_NOISE = re.compile(r"\(.*?\)|\bv?\d+(?:\.\d+)*\b")


def core_name(name: str) -> str:
    """'WinRAR 7.13 (64-bit)' -> 'WinRAR'."""
    return re.sub(r"\s+", " ", _NAME_NOISE.sub(" ", name)).strip() or name


# ---------------------------------------------------------------- phonetic key
# Speech-to-text often writes English names in Thai ("กิตทับ" for GitHub). Both
# scripts are reduced to a consonant-sound skeleton and compared: กิตทับ -> ktp,
# github -> ktp. Vowels, tone marks and silent letters are dropped.

_THAI_SOUNDS = {
    "k": "กขฃคฅฆ", "N": "ง", "c": "จฉชฌ", "s": "ซศษส", "y": "ญย", "t": "ฎฏฐฑฒดตถทธ",
    "n": "ณน", "p": "บปผพภ", "f": "ฝฟ", "m": "ม", "r": "รลฬฤฦ", "w": "ว",
}
_THAI_MAP = {ch: key for key, chars in _THAI_SOUNDS.items() for ch in chars}
# A consonant ending a Thai word is pronounced as one of few final sounds:
# คลอส / คลอด / คลอต all end in /t/, so "คลอส" must match Claude (krt).
_THAI_FINALS = {
    "k": "กขฃคฅฆ", "t": "จฉชซฌฎฏฐฑฒดตถทธศษส", "p": "บปผพภฝฟ",
    "n": "ญณนรลฬ", "m": "ม", "N": "ง", "y": "ย", "w": "ว",
}
_THAI_FINAL_MAP = {ch: key for key, chars in _THAI_FINALS.items() for ch in chars}
_THAI_TONES = "่้๊๋"
_EN_FINALS = {"s": "t", "c": "t", "f": "p"}   # same idea for the last sound of an English word
_THAI_CHARS = re.compile(r"[฀-๿]")
_THAI_SILENT = re.compile(r"[ก-ฮ][ะ-ฺ็-๋]*์")  # letter + ์
_EN_RULES = [  # applied in order, on lowercase latin text
    (r"chr", "kr"), (r"ch|j|dge", "c"), (r"sh", "s"), (r"ph", "f"), (r"th", "t"), (r"ck", "k"),
    (r"ng", "N"), (r"c(?=[eiy])", "s"), (r"[cqg]", "k"), (r"x", "ks"), (r"z", "s"), (r"d", "t"),
    (r"b", "p"), (r"v", "w"), (r"l", "r"), (r"h", ""),
    (r"(?<=[aeiou])r(?![aeiou])", ""),   # "work" -> wk, like Thai เวิร์ค
    (r"(?<!^)y", ""), (r"[aeiou]", ""),
]


def phonetic_key(text: str) -> str:
    text = _THAI_SILENT.sub("", normalize(text))
    out = []
    for word in re.findall(r"[a-z]+|[฀-๿]+", text):
        if word[0] <= "z":
            for pattern, repl in _EN_RULES:
                word = re.sub(pattern, repl, word)
            word = re.sub(r"(.)\1+", r"\1", word)   # "compass" -> kmps before the final
            if word and word[-1] in _EN_FINALS:
                word = word[:-1] + _EN_FINALS[word[-1]]
            out.append(word)
        else:
            keys = [_THAI_MAP.get(ch, "") for ch in word]
            stem = word.rstrip(_THAI_TONES)
            if stem and stem[-1] in _THAI_FINAL_MAP and len(stem) > 1:   # ends in a consonant
                keys[len(stem) - 1] = _THAI_FINAL_MAP[stem[-1]]
            out.append("".join(keys))
    return re.sub(r"(.)\1+", r"\1", "".join(out))  # collapse doubles: kk -> k


def score(query: str, candidate: str) -> float:
    """0..1 similarity. Best of:

    - spelling vs whole name ("chrome" vs "Chrome" = 1.0)
    - 0.9 x spelling vs one word of the name ("chrome" vs "Google Chrome" = 0.9)
    - 0.9 x sound skeleton ("กิตทับ" vs "github" = 0.9). Phonetic hits never
      reach a perfect score, so near-misses land in the ask-first band.
    """
    q, c = _compact(query), _compact(candidate)
    if not q or not c:
        return 0.0
    if q == c or q == _compact(core_name(candidate)):
        return 1.0
    ratio = SequenceMatcher(None, q, c).ratio()
    words = normalize(core_name(candidate)).split()
    if len(words) > 1:
        word_ratio = max(SequenceMatcher(None, q, w).ratio() for w in words)
        ratio = max(ratio, 0.9 * word_ratio)

    # Sound match only for Thai-script queries; Latin vs Latin is covered by spelling above.
    if _THAI_CHARS.search(query):
        qk = phonetic_key(query)
        keys = [phonetic_key(core_name(candidate))]
        keys += [k for k in (phonetic_key(w) for w in words) if len(k) >= 3] if len(words) > 1 else []
        if len(qk) >= 2:
            for ck in keys:
                if len(ck) >= 2:
                    ratio = max(ratio, 0.9 * SequenceMatcher(None, qk, ck).ratio())
    return ratio


def verb_score(heard: str, verb: str) -> float:
    """Stricter than score(): a verb decides WHAT happens, so spelling must also be close.

    0.4 x spelling + 0.6 x sound. "คนหา"/"ค้นหา" = 0.96, "คุณหา" = 0.84, "ขน"/"ค้นหา" = 0.4.
    """
    h, v = _compact(heard), _compact(verb)
    hk, vk = phonetic_key(heard), phonetic_key(verb)
    if not h or not hk or not vk:
        return 0.0
    return 0.4 * SequenceMatcher(None, h, v).ratio() + 0.6 * SequenceMatcher(None, hk, vk).ratio()


def best_match(query: str, candidates) -> tuple[str | None, float]:
    """Return (best candidate, score) from an iterable of names."""
    best, best_score = None, 0.0
    for candidate in candidates:
        s = score(query, candidate)
        if s > best_score:
            best, best_score = candidate, s
    return best, best_score
