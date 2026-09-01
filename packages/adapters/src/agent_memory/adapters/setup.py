"""Self-install: probe the host, write its hook dialect, leave everything else alone."""

from __future__ import annotations

import json
import pathlib

from . import moments

HOOK_COMMAND = "mem-hook"
CLAUDE_SETTINGS = pathlib.Path("~/.claude/settings.json")
CODEX_SETTINGS = pathlib.Path("~/.codex/hooks.json")
HOOKS_KEY = "hooks"
MATCHER_KEY = "matcher"
ANY_MATCHER = "*"

SETTINGS_FOR = {
    moments.HOST_CLAUDE_CODE: CLAUDE_SETTINGS,
    moments.HOST_CODEX: CODEX_SETTINGS,
}


def detect() -> list[str]:
    return [host for host, path in SETTINGS_FOR.items() if path.expanduser().parent.exists()]


def install(host: str, settings_path: pathlib.Path | None = None) -> pathlib.Path:
    target = settings_path or SETTINGS_FOR[host].expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    settings = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
    hooks = settings.setdefault(HOOKS_KEY, {})
    for event in moments.DIALECTS[host]:
        entries = hooks.setdefault(event, [])
        if not any(_mentions_command(entry) for entry in entries):
            entries.append(
                {
                    MATCHER_KEY: ANY_MATCHER,
                    HOOKS_KEY: [{"type": "command", "command": HOOK_COMMAND}],
                }
            )
    rendered = json.dumps(settings, indent=SETTINGS_INDENT, sort_keys=True)
    target.write_text(rendered, encoding="utf-8")
    return target


def _mentions_command(entry: object) -> bool:
    return HOOK_COMMAND in json.dumps(entry)


SETTINGS_INDENT = 2
