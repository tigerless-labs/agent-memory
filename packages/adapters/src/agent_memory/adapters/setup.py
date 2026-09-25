"""Self-install: probe the host, write its hook dialect, leave everything else alone."""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import tempfile

from agent_memory.core.errors import FieldError, ValidationError

from . import moments

HOOK_COMMAND = "mem-hook"
CLAUDE_SETTINGS = pathlib.Path("~/.claude/settings.json")
CODEX_SETTINGS = pathlib.Path("~/.codex/hooks.json")
MUSE_SETTINGS = pathlib.Path("muse/settings.json")
HOOKS_KEY = "hooks"
MATCHER_KEY = "matcher"
ANY_MATCHER = "*"

SETTINGS_FOR = {
    moments.HOST_CLAUDE_CODE: CLAUDE_SETTINGS,
    moments.HOST_CODEX: CODEX_SETTINGS,
    moments.HOST_MUSE_CODE: MUSE_SETTINGS,
}
ALIASES = {"muse": moments.HOST_MUSE_CODE}
MUSE_SCHEMA_VERSION = 1
MUSE_BINARY = "muse"


def detect() -> list[str]:
    return [host for host in SETTINGS_FOR if default_settings_path(host).parent.exists()]


def canonical_host(host: str) -> str:
    canonical = ALIASES.get(host, host)
    if canonical not in SETTINGS_FOR:
        supported = ", ".join(sorted(SETTINGS_FOR))
        raise ValidationError(
            [FieldError("host", f"unsupported host {host!r}; choose {supported}")]
        )
    return canonical


def default_settings_path(host: str, environment: dict[str, str] | None = None) -> pathlib.Path:
    canonical = canonical_host(host)
    if canonical == moments.HOST_MUSE_CODE:
        env = os.environ if environment is None else environment
        fallback = pathlib.Path(env.get("HOME", "~")).expanduser() / ".config"
        config_home = pathlib.Path(env.get("XDG_CONFIG_HOME") or fallback)
        return config_home / MUSE_SETTINGS
    return SETTINGS_FOR[canonical].expanduser()


def probe(host: str) -> str:
    canonical = canonical_host(host)
    if canonical != moments.HOST_MUSE_CODE:
        return ""
    binary = MUSE_BINARY
    resolved = shutil.which(binary)
    if resolved is None:
        raise ValidationError(
            [FieldError("host", f"{canonical} requires `{binary}` on PATH; install it and retry")]
        )
    try:
        completed = subprocess.run(
            [resolved, "--version"], capture_output=True, text=True, check=False, timeout=10
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValidationError(
            [FieldError("host", f"could not run `{binary} --version`: {error}")]
        ) from error
    version = (completed.stdout.strip() or completed.stderr.strip()).splitlines()
    if completed.returncode != 0:
        detail = version[0] if version else f"exit {completed.returncode}"
        raise ValidationError(
            [FieldError("host", f"`{binary} --version` failed: {detail}")]
        )
    return version[0] if version else "unknown"


def install(host: str, settings_path: pathlib.Path | None = None) -> pathlib.Path:
    host = canonical_host(host)
    target = settings_path or default_settings_path(host)
    target.parent.mkdir(parents=True, exist_ok=True)
    settings = _read_settings(target)
    if host == moments.HOST_MUSE_CODE:
        settings.setdefault("schema_version", MUSE_SCHEMA_VERSION)
    hooks = settings.setdefault(HOOKS_KEY, {})
    if not isinstance(hooks, dict):
        raise ValidationError([FieldError("settings.hooks", "must be an object")])
    command = _hook_command(host)
    for event in moments.DIALECTS[host]:
        entries = hooks.setdefault(event, [])
        if not isinstance(entries, list):
            raise ValidationError([FieldError(f"settings.hooks.{event}", "must be an array")])
        if not any(_mentions_command(entry) for entry in entries):
            entries.append(
                {
                    MATCHER_KEY: ANY_MATCHER,
                    HOOKS_KEY: [{"type": "command", "command": command}],
                }
            )
    rendered = json.dumps(settings, indent=SETTINGS_INDENT, sort_keys=True) + "\n"
    if not target.exists() or target.read_text(encoding="utf-8") != rendered:
        _atomic_write(target, rendered)
    return target


def _read_settings(target: pathlib.Path) -> dict[str, object]:
    if not target.exists():
        return {}
    try:
        parsed = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValidationError(
            [FieldError("settings", f"malformed JSON in {target}: {error.msg}")]
        ) from error
    if not isinstance(parsed, dict):
        raise ValidationError([FieldError("settings", f"{target} must contain a JSON object")])
    return parsed


def _hook_command(host: str) -> str:
    return f"{HOOK_COMMAND} --host {host}" if host == moments.HOST_MUSE_CODE else HOOK_COMMAND


def _atomic_write(target: pathlib.Path, rendered: str) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    path = pathlib.Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
        path.replace(target)
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _mentions_command(entry: object) -> bool:
    return HOOK_COMMAND in json.dumps(entry)


SETTINGS_INDENT = 2
