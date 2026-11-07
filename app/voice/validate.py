"""Check and resolve an Action before it runs (shared by rules and LLM).

- Only registry actions, only declared string args.
- Names are mapped to known targets (app index / sites / modes); callers can
  never supply a path or arbitrary URL.
"""
from __future__ import annotations

from dataclasses import dataclass

from voice.actions import REGISTRY, Action, ActionContext, ActionSpec, Risk
from voice.matching import best_match

AUTO_THRESHOLD = 0.85   # at or above: run without asking (SAFE actions)
ASK_THRESHOLD = 0.6     # between: ask "did you mean X?"; below: reject
MAX_ARG_LENGTH = 200


class Rejected(Exception):
    """Action cannot run. Message is shown to the user."""


@dataclass
class Resolved:
    action: Action          # args resolved: canonical names, real path/url
    spec: ActionSpec
    score: float
    label: str              # human readable, for confirm dialogs and logs

    @property
    def needs_confirm(self) -> bool:
        return self.spec.risk != Risk.SAFE or self.score < AUTO_THRESHOLD


def resolve(action: Action, ctx: ActionContext) -> Resolved:
    spec = REGISTRY.get(action.name)
    if spec is None:
        raise Rejected(f"Unknown action: {action.name}")
    args = _check_args(action.args, spec)

    if spec.name == "web_search":
        return Resolved(Action("web_search", {"query": args["query"]}), spec, 1.0,
                        f"ค้นหา \"{args['query']}\"")
    if spec.name == "open_url":
        return _resolve_target(args["site"], ctx, kinds=("site",))
    if spec.name == "run_mode":
        return _resolve_target(args["name"], ctx, kinds=("mode",))
    if spec.name == "open_app":
        # "เปิด X" may also mean a site or a mode; pick the best match, apps win ties.
        return _resolve_target(args["name"], ctx, kinds=("app", "site", "mode"))
    raise Rejected(f"No resolver for action: {spec.name}")


def _check_args(args, spec: ActionSpec) -> dict:
    if not isinstance(args, dict):
        raise Rejected("Arguments must be an object.")
    unknown = set(args) - set(spec.params)
    if unknown:
        raise Rejected(f"Unexpected arguments: {', '.join(sorted(unknown))}")
    clean = {}
    for key, value in args.items():
        if not isinstance(value, str) or not value.strip():
            raise Rejected(f"'{key}' must be non-empty text.")
        if len(value) > MAX_ARG_LENGTH:
            raise Rejected(f"'{key}' is too long.")
        clean[key] = value.strip()
    missing = [k for k in spec.required if k not in clean]
    if missing:
        raise Rejected(f"Missing: {', '.join(missing)}")
    return clean


def _resolve_target(term: str, ctx: ActionContext, kinds: tuple[str, ...]) -> Resolved:
    # 1. Alias (e.g. "ไลน์" -> "line") may also redirect to another kind.
    alias, alias_score = best_match(term, ctx.aliases)
    if alias is not None and alias_score >= AUTO_THRESHOLD:
        target, kind = ctx.aliases[alias]
        if kind in kinds:
            term, kinds = target, (kind,)

    # 2. Best candidate across allowed kinds. Order = tie-break priority.
    pools = {"app": ctx.apps, "site": ctx.sites, "mode": ctx.modes}
    best_kind, best_name, best_score = None, None, 0.0
    for kind in kinds:
        name, s = best_match(term, pools[kind])
        if s > best_score:
            best_kind, best_name, best_score = kind, name, s

    if best_name is None or best_score < ASK_THRESHOLD:
        raise Rejected(f"ไม่พบ \"{term}\"")

    if best_kind == "app":
        action = Action("open_app", {"name": best_name, "path": ctx.apps[best_name]})
        label = f"เปิดโปรแกรม {best_name}"
    elif best_kind == "site":
        action = Action("open_url", {"site": best_name, "url": ctx.sites[best_name]})
        label = f"เปิดเว็บ {best_name}"
    else:
        action = Action("run_mode", {"name": best_name})
        label = f"เข้าโหมด {best_name}"
    return Resolved(action, REGISTRY[action.name], best_score, label)
