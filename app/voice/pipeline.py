"""Text -> resolved actions -> execution. Audio-free, so it is unit-testable.

v2.1 adds an LLM step in interpret() when the rules return nothing.

Learning: when the user confirms an uncertain match ("มงโกดีบี คอมพาส ใช่ไหม?" -> yes)
or picks a target from suggest(), the spoken term is saved as an alias, so the
same words run without asking next time. Only explicit user choices are learned.
"""
from __future__ import annotations

from typing import Callable

from voice import intents
from voice.actions import ActionContext, Risk
from voice.matching import normalize
from voice.validate import AUTO_THRESHOLD, Rejected, Resolved, resolve

MAX_ACTIONS = 5
COUNTDOWN_SECONDS = 30   # Risk.CRITICAL (shutdown/restart): last chance to cancel after "yes"

Countdown = Callable[[str, int], bool]   # (label, seconds) -> True = go ahead, False = cancelled
MIN_ALIAS_LENGTH = 2
ALIAS_KINDS = ("app", "site", "mode")

SaveAlias = Callable[[str, str, str], None]   # (alias, target, kind), e.g. database.write_alias


def interpret_detail(text: str, ctx: ActionContext) -> tuple[list[Resolved], list[Rejected]]:
    """Return (runnable actions, rejections). Rejected.term is set for unknown names."""
    actions = intents.parse(text)
    if not actions:
        return [], [Rejected(f"ไม่เข้าใจคำสั่ง \"{text}\"")]

    resolved, rejected = [], []
    for action in actions[:MAX_ACTIONS]:
        try:
            resolved.append(resolve(action, ctx))
        except Rejected as exc:
            rejected.append(exc)
    return resolved, rejected


def interpret(text: str, ctx: ActionContext) -> tuple[list[Resolved], list[str]]:
    """Return (runnable actions, rejection messages)."""
    resolved, rejected = interpret_detail(text, ctx)
    return resolved, [str(exc) for exc in rejected]


FALLBACK_KINDS = ("web_search", "play_music")   # picker extras: run once, never learned
PICK_LIMIT = 6   # known targets shown; misheard names often have several look-alikes (OneNote x3)


def picker_options(term: str, ctx: ActionContext) -> list[tuple[str, str, float]]:
    """Closest known targets, then "search it" / "play it" so any phrase has a way out."""
    from voice.validate import suggest

    return suggest(term, ctx, limit=PICK_LIMIT) + [(kind, term, 0.0) for kind in FALLBACK_KINDS]


def apply_pick(choice: tuple[str, str] | None, term: str, text: str, ctx: ActionContext,
               save: SaveAlias | None = None) -> tuple[list[Resolved], list[Rejected]]:
    """Turn a picker choice into runnable actions.

    Known target -> learn alias, re-interpret the whole sentence.
    Fallback (search / music) -> run that action on the spoken term, nothing learned.
    """
    if not choice:
        return [], [Rejected(f"ไม่พบ \"{term}\"", term=term)]
    kind, name = choice
    if kind in FALLBACK_KINDS:
        from voice.actions import Action

        return [resolve(Action(kind, {"query": name}), ctx)], []
    if learn_alias(term, kind, name, ctx, save):
        return interpret_detail(text, ctx)
    return [], [Rejected(f"ไม่พบ \"{term}\"", term=term)]


def declined_term(results: list[tuple[Resolved, str]]) -> str | None:
    """Spoken name of a guessed target the user said "no" to, so the UI can offer the picker.

    "เปิดโน๊ด" -> "OneNote ใช่ไหม?" -> no -> pick Notepad -> "โน๊ด" is learned.
    Only uncertain name matches: a confident target that was declined is just cancelled.
    """
    for item, outcome in results:
        if outcome == "cancelled" and item.kind and item.heard and item.match < AUTO_THRESHOLD:
            return item.heard
    return None


def history_record(resolved: list[Resolved], results: list[tuple[Resolved, str]] | None,
                   source: str = "rule") -> tuple[str, list[dict], str]:
    """(source, actions, result) for database.add_history()."""
    actions = [{"name": r.action.name, "args": {k: v for k, v in r.action.args.items() if k != "path"},
                "score": round(r.score, 2)} for r in resolved]
    if not resolved:
        return "none", actions, "rejected"
    outcomes = [outcome for _, outcome in results or []]
    if any(o.startswith("error") for o in outcomes):
        result = "error"
    elif outcomes and all(o == "cancelled" for o in outcomes):
        result = "cancelled"
    else:
        result = "done"
    return source, actions, result


def learn_alias(heard: str, kind: str, target: str, ctx: ActionContext,
                save: SaveAlias | None = None) -> bool:
    """Remember `heard` -> target. Returns False if the term is unusable."""
    alias = normalize(heard)
    if kind not in ALIAS_KINDS or len(alias.replace(" ", "")) < MIN_ALIAS_LENGTH:
        return False
    if normalize(target) == alias:
        return False   # already matches exactly; nothing to learn
    ctx.aliases[alias] = (target, kind)
    if save is not None:
        save(alias, target, kind)
    return True


def execute(
    resolved: list[Resolved],
    ctx: ActionContext,
    confirm: Callable[[str], bool],
    save_alias: SaveAlias | None = None,
    countdown: Countdown | None = None,
) -> list[tuple[Resolved, str]]:
    """Run actions. `confirm(question)` must return False on cancel/timeout.

    Risk.CRITICAL also needs `countdown(label, seconds)` to return True; without a
    countdown callback a critical action never runs.
    A confirmed uncertain name match is learned as an alias (via `save_alias`).
    """
    results = []
    for item in resolved:
        if item.needs_confirm:
            if not confirm(f"{item.label} ใช่ไหม?"):
                results.append((item, "cancelled"))
                continue
            if item.match < AUTO_THRESHOLD and item.kind and item.heard:
                learn_alias(item.heard, item.kind, item.target, ctx, save_alias)
        if item.spec.risk == Risk.CRITICAL:
            if countdown is None or not countdown(item.label, COUNTDOWN_SECONDS):
                results.append((item, "cancelled"))
                continue
        try:
            results.append((item, item.spec.handler(item.action.args, ctx)))
        except Exception as exc:  # handler failure must not stop the app
            results.append((item, f"error: {exc}"))
    return results
