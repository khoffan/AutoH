"""Text -> resolved actions -> execution. Audio-free, so it is unit-testable.

v2.1 adds an LLM step in interpret() when the rules return nothing.
"""
from __future__ import annotations

from typing import Callable

from voice import intents
from voice.actions import ActionContext
from voice.validate import Rejected, Resolved, resolve

MAX_ACTIONS = 5


def interpret(text: str, ctx: ActionContext) -> tuple[list[Resolved], list[str]]:
    """Return (runnable actions, rejection messages)."""
    actions = intents.parse(text)
    if not actions:
        return [], [f"ไม่เข้าใจคำสั่ง \"{text}\""]

    resolved, errors = [], []
    for action in actions[:MAX_ACTIONS]:
        try:
            resolved.append(resolve(action, ctx))
        except Rejected as exc:
            errors.append(str(exc))
    return resolved, errors


def execute(
    resolved: list[Resolved],
    ctx: ActionContext,
    confirm: Callable[[str], bool],
) -> list[tuple[Resolved, str]]:
    """Run actions. `confirm(question)` must return False on cancel/timeout."""
    results = []
    for item in resolved:
        if item.needs_confirm and not confirm(f"{item.label} ใช่ไหม?"):
            results.append((item, "cancelled"))
            continue
        try:
            results.append((item, item.spec.handler(item.action.args, ctx)))
        except Exception as exc:  # handler failure must not stop the app
            results.append((item, f"error: {exc}"))
    return results
