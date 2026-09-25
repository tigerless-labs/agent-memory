"""Self-install: probe the host, write its hook dialect and skill, leave everything else alone."""

from __future__ import annotations

import json
import pathlib
import sys

from agent_memory.core import prompts

from . import moments

HOOK_COMMAND = "mem-hook"
HOST_FLAG = "--host"
CLAUDE_SETTINGS = pathlib.Path("~/.claude/settings.json")
CODEX_SETTINGS = pathlib.Path("~/.codex/hooks.json")
HOOKS_KEY = "hooks"
MATCHER_KEY = "matcher"
ANY_MATCHER = "*"
SKILL_PATH = pathlib.Path("skills") / "agent-memory" / "SKILL.md"
SETTINGS_INDENT = 2

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
    entry = {
        MATCHER_KEY: ANY_MATCHER,
        HOOKS_KEY: [{"type": "command", "command": hook_command(host)}],
    }
    for event in moments.DIALECTS[host]:
        kept = [existing for existing in hooks.get(event, []) if not _mentions_command(existing)]
        hooks[event] = [*kept, entry]
    rendered = json.dumps(settings, indent=SETTINGS_INDENT, sort_keys=True)
    target.write_text(rendered, encoding="utf-8")
    _install_skill(target.parent / SKILL_PATH)
    return target


def hook_command(host: str) -> str:
    """By absolute path: desktop clients run hooks without the user's shell PATH."""
    return f"{pathlib.Path(sys.executable).parent / HOOK_COMMAND} {HOST_FLAG} {host}"


def _install_skill(path: pathlib.Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(prompts.skill(), encoding="utf-8")


def _mentions_command(entry: object) -> bool:
    return HOOK_COMMAND in json.dumps(entry)
