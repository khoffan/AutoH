"""Check and resolve an Action before it runs (shared by rules and LLM).

- Only registry actions, only declared string args.
- Names are mapped to known targets (app index / sites / modes); callers can
  never supply a path or arbitrary URL.
"""
from __future__ import annotations

from dataclasses import dataclass

from voice.actions import (
    FOLDERS, REGISTRY, SETTINGS, Action, ActionContext, ActionSpec, Risk, known_folder_path,
)
from voice.matching import best_match

AUTO_THRESHOLD = 0.85   # at or above: run without asking (SAFE actions)
ASK_THRESHOLD = 0.6     # between: ask "did you mean X?"; below: reject
MAX_ARG_LENGTH = 200


class Rejected(Exception):
    """Action cannot run. Message is shown to the user.

    `term` is set when a spoken name matched nothing, so the UI can offer suggest(term).
    """

    def __init__(self, message: str, term: str | None = None):
        super().__init__(message)
        self.term = term


@dataclass
class Resolved:
    action: Action          # args resolved: canonical names, real path/url
    spec: ActionSpec
    score: float            # min(verb confidence, target match)
    label: str              # human readable, for confirm dialogs and logs
    heard: str = ""         # target as spoken, before resolution ("ร้าย"); "" for searches
    match: float = 1.0      # name-match score alone (score also includes verb confidence)

    @property
    def needs_confirm(self) -> bool:
        return self.spec.risk != Risk.SAFE or self.score < AUTO_THRESHOLD

    @property
    def kind(self) -> str | None:
        """Alias kind of the resolved target, or None (search)."""
        return {"open_app": "app", "open_url": "site", "run_mode": "mode"}.get(self.action.name)

    @property
    def target(self) -> str | None:
        return self.action.args.get("name") or self.action.args.get("site")


def resolve(action: Action, ctx: ActionContext) -> Resolved:
    spec = REGISTRY.get(action.name)
    if spec is None:
        raise Rejected(f"Unknown action: {action.name}")
    args = _check_args(action.args, spec)

    if spec.name == "web_search":
        resolved = Resolved(Action("web_search", {"query": args["query"]}), spec, 1.0,
                            f"ค้นหา \"{args['query']}\"")
    elif spec.name == "open_url":
        resolved = _resolve_target(args["site"], ctx, kinds=("site",))
    elif spec.name == "run_mode":
        resolved = _resolve_target(args["name"], ctx, kinds=("mode",))
    elif spec.name == "open_app":
        # "เปิด X" may also mean a site or a mode; pick the best match, apps win ties.
        resolved = _resolve_target(args["name"], ctx, kinds=("app", "site", "mode"))
    elif spec.name == "play_music":
        resolved = Resolved(Action("play_music", {"query": args["query"]}), spec, 1.0,
                            f"เล่น \"{args['query']}\" บน YouTube")
    elif spec.name == "open_folder":
        key, s = _match_fixed(args["name"], FOLDERS, "โฟลเดอร์")
        folder = FOLDERS[key]
        resolved = Resolved(Action("open_folder", {"name": folder, "path": known_folder_path(folder)}),
                            spec, s, f"เปิดโฟลเดอร์ {folder}")
    elif spec.name == "open_settings":
        key, s = _match_fixed(args["page"], SETTINGS, "หน้าตั้งค่า")
        resolved = Resolved(Action("open_settings", {"page": key, "uri": SETTINGS[key]}),
                            spec, s, f"เปิดตั้งค่า {key}")
    else:
        raise Rejected(f"No resolver for action: {spec.name}")

    # A guessed verb lowers trust in the whole command.
    resolved.score = min(resolved.score, action.confidence)
    return resolved


FIXED_MIN = 0.75   # folder/settings names are short and few: weak guesses are noise


def _match_fixed(term: str, table: dict, what: str) -> tuple[str, float]:
    """Match against a fixed whitelist (folders, settings pages)."""
    key, s = best_match(term, table)
    if key is None or s < FIXED_MIN:
        raise Rejected(f"ไม่รู้จัก{what} \"{term}\"")
    return key, s


def suggest(term: str, ctx: ActionContext, limit: int = 5, minimum: float = 0.3):
    """Closest targets for a "did you mean...?" picker: [(kind, name, score)], best first."""
    from voice.matching import score

    pools = {"app": ctx.apps, "site": ctx.sites, "mode": ctx.modes}
    ranked = sorted(
        ((kind, name, score(term, name)) for kind, pool in pools.items() for name in pool),
        key=lambda item: item[2], reverse=True,
    )
    return [item for item in ranked if item[2] >= minimum][:limit]


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
    heard = term
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
        raise Rejected(f"ไม่พบ \"{term}\"", term=heard)

    if best_kind == "app":
        action = Action("open_app", {"name": best_name, "path": ctx.apps[best_name]})
        label = f"เปิดโปรแกรม {best_name}"
    elif best_kind == "site":
        action = Action("open_url", {"site": best_name, "url": ctx.sites[best_name]})
        label = f"เปิดเว็บ {best_name}"
    else:
        action = Action("run_mode", {"name": best_name})
        label = f"เข้าโหมด {best_name}"
    return Resolved(action, REGISTRY[action.name], best_score, label, heard=heard, match=best_score)
