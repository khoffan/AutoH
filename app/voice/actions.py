"""Action registry shared by the rule parser (v2.0) and the LLM interpreter (v2.1).

Every action the app can perform is declared here once. Nothing outside this
registry can be executed from voice input.
"""
from __future__ import annotations

import webbrowser
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable
from urllib.parse import quote_plus


class Risk(str, Enum):
    SAFE = "safe"            # run without asking (if the name match is confident)
    CONFIRM = "confirm"      # always ask first
    CRITICAL = "critical"    # ask first + cancellable countdown (v2.1)


@dataclass
class Action:
    name: str
    args: dict = field(default_factory=dict)
    confidence: float = 1.0   # < 1.0 when the verb itself was guessed (fuzzy), see intents


@dataclass
class ActionContext:
    """Everything handlers and the resolver may use. Side effects are injectable for tests."""

    apps: dict[str, str]                       # app name -> path (app_index)
    modes: dict[str, dict]                     # from load_config()["modes"]
    aliases: dict[str, tuple[str, str]]        # spoken alias -> (target, kind)
    sites: dict[str, str] = field(default_factory=lambda: dict(SITES))
    open_app: Callable[[str, str], None] | None = None   # (path, name)
    open_url: Callable[[str], None] = webbrowser.open
    run_mode: Callable[[str], None] | None = None


@dataclass(frozen=True)
class ActionSpec:
    name: str
    description: str
    params: dict                     # JSON-schema "properties"
    required: tuple[str, ...]
    risk: Risk
    handler: Callable[[dict, ActionContext], str]


SITES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "facebook": "https://www.facebook.com",
    "github": "https://github.com",
    "chatgpt": "https://chatgpt.com",
    "claude": "https://claude.ai",
}

REGISTRY: dict[str, ActionSpec] = {}


def register(spec: ActionSpec) -> None:
    REGISTRY[spec.name] = spec


def tool_definitions() -> list[dict]:
    """Registry as LLM tool definitions (v2.1)."""
    return [
        {
            "name": spec.name,
            "description": spec.description,
            "input_schema": {
                "type": "object",
                "properties": spec.params,
                "required": list(spec.required),
            },
        }
        for spec in REGISTRY.values()
    ]


# ---------------------------------------------------------------- handlers
# Handlers receive args already resolved by validate.resolve() (canonical names, real paths).

def _open_app(args: dict, ctx: ActionContext) -> str:
    if ctx.open_app is None:
        # Like clicking the icon: focus if running, launch if not (modes use safe_open_app).
        from core.launcher import open_or_focus

        how = open_or_focus(args["path"], args["name"])
        return f"{how} app {args['name']}"
    ctx.open_app(args["path"], args["name"])
    return f"opened app {args['name']}"


def _open_url(args: dict, ctx: ActionContext) -> str:
    ctx.open_url(args["url"])
    return f"opened {args['url']}"


def _web_search(args: dict, ctx: ActionContext) -> str:
    ctx.open_url("https://www.google.com/search?q=" + quote_plus(args["query"]))
    return f"searched {args['query']}"


def _run_mode(args: dict, ctx: ActionContext) -> str:
    if ctx.run_mode is None:
        raise RuntimeError("run_mode is not available")
    ctx.run_mode(args["name"])
    return f"ran mode {args['name']}"


_NAME = {"name": {"type": "string", "description": "Name as the user said it."}}

register(ActionSpec(
    "open_app", "Open an installed program by name.", _NAME, ("name",), Risk.SAFE, _open_app,
))
register(ActionSpec(
    "open_url", "Open a known website by name (e.g. youtube, gmail).",
    {"site": {"type": "string", "description": "Website name."}}, ("site",), Risk.SAFE, _open_url,
))
register(ActionSpec(
    "web_search", "Search the web in the default browser.",
    {"query": {"type": "string", "description": "Search text."}}, ("query",), Risk.SAFE, _web_search,
))
register(ActionSpec(
    "run_mode", "Run a saved AutoH mode (opens its apps and URLs).", _NAME, ("name",), Risk.SAFE,
    _run_mode,
))
