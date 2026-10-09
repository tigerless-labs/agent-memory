"""Deterministic host configuration primitives shared by setup and doctor."""

from __future__ import annotations

import json
import os
import pathlib
import shlex
import shutil
import subprocess
import sys
import tempfile

from agent_memory.core import prompts
from agent_memory.core.errors import FieldError, ValidationError

from . import moments

HOOK_COMMAND = "mem-hook"
HOST_FLAG = "--host"
CLAUDE_SETTINGS = pathlib.Path("~/.claude/settings.json")
CODEX_SETTINGS = pathlib.Path("~/.codex/hooks.json")
MUSE_SETTINGS = pathlib.Path("muse/settings.json")
HOOKS_KEY = "hooks"
MATCHER_KEY = "matcher"
ANY_MATCHER = "*"
SKILL_PATH = pathlib.Path("skills") / "agent-memory" / "SKILL.md"
SETTINGS_INDENT = 2

SETTINGS_FOR = {
    moments.HOST_CLAUDE_CODE: CLAUDE_SETTINGS,
    moments.HOST_CODEX: CODEX_SETTINGS,
    moments.HOST_MUSE_CODE: MUSE_SETTINGS,
}
ALIASES = {"muse": moments.HOST_MUSE_CODE}
MUSE_SCHEMA_VERSION = 1
MUSE_DATA_HOME_FLAG = "--muse-data-home"
MUSE_SETTINGS_FLAG = "--muse-settings"
MUSE_LAUNCHER_FLAG = "--muse-launcher"
MUSE_BINARY_FLAG = "--muse-binary"
STORE_FLAG = "--store"
MCP_SERVER = "agent-memory"
MCP_COMMAND = "mem-mcp"
BINARIES = {
    moments.HOST_CLAUDE_CODE: "claude",
    moments.HOST_CODEX: "codex",
    moments.HOST_MUSE_CODE: "muse",
}


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
    binary = BINARIES[canonical]
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


def install(
    host: str,
    settings_path: pathlib.Path | None = None,
    store_root: pathlib.Path | None = None,
    *,
    provider: str | None = None,
    model: str | None = None,
    provider_url: str | None = None,
    muse_launcher: pathlib.Path | None = None,
    muse_binary: pathlib.Path | None = None,
    mcp: bool = False,
    lifecycle: bool = True,
) -> pathlib.Path:
    host = canonical_host(host)
    target = settings_path or default_settings_path(host)
    target.parent.mkdir(parents=True, exist_ok=True)
    settings = _read_settings(target)
    if host == moments.HOST_MUSE_CODE:
        settings.setdefault("schema_version", MUSE_SCHEMA_VERSION)
        if provider:
            from . import openrouter

            openrouter.merge_routing(
                settings,
                provider=provider,
                model=model,
                **({"proxy_url": provider_url} if provider_url else {}),
            )
        if mcp:
            _merge_json_mcp(settings, host, store_root)
    if lifecycle:
        hooks = settings.setdefault(HOOKS_KEY, {})
        if not isinstance(hooks, dict):
            raise ValidationError([FieldError("settings.hooks", "must be an object")])
        entry = {
            MATCHER_KEY: ANY_MATCHER,
            HOOKS_KEY: [
                {
                    "type": "command",
                    "command": hook_command(
                        host,
                        store_root,
                        settings_path=target,
                        muse_launcher=muse_launcher,
                        muse_binary=muse_binary,
                    ),
                }
            ],
        }
        for event in moments.DIALECTS[host]:
            entries = hooks.get(event, [])
            if not isinstance(entries, list):
                raise ValidationError(
                    [FieldError(f"settings.hooks.{event}", "must be an array")]
                )
            kept = [existing for existing in entries if not _mentions_command(existing)]
            hooks[event] = [*kept, entry]
    rendered = json.dumps(settings, indent=SETTINGS_INDENT, sort_keys=True) + "\n"
    if not target.exists() or target.read_text(encoding="utf-8") != rendered:
        _atomic_write(target, rendered)
    _install_skill(target.parent / SKILL_PATH)
    if mcp and host != moments.HOST_MUSE_CODE:
        _install_external_mcp(host, target, store_root)
    return target


def hook_command(
    host: str,
    store_root: pathlib.Path | None = None,
    *,
    settings_path: pathlib.Path | None = None,
    muse_launcher: pathlib.Path | None = None,
    muse_binary: pathlib.Path | None = None,
) -> str:
    """By absolute path: desktop clients run hooks without the user's shell PATH."""
    command = [str(pathlib.Path(sys.executable).parent / HOOK_COMMAND), HOST_FLAG, host]
    if host == moments.HOST_MUSE_CODE:
        command += [MUSE_DATA_HOME_FLAG, str(_muse_data_home())]
        target = settings_path or default_settings_path(host)
        command += [MUSE_SETTINGS_FLAG, str(target.expanduser().resolve())]
        if muse_launcher is not None:
            command += [MUSE_LAUNCHER_FLAG, str(muse_launcher.expanduser().resolve())]
        if muse_binary is not None:
            command += [MUSE_BINARY_FLAG, str(muse_binary.expanduser().resolve())]
    if store_root is not None:
        command += [STORE_FLAG, str(pathlib.Path(store_root).resolve())]
    return shlex.join(command)


def skill_path(host: str, settings_path: pathlib.Path | None = None) -> pathlib.Path:
    target = settings_path or default_settings_path(host)
    return target.parent / SKILL_PATH


def mcp_binary() -> str:
    """Use the sibling entry point for the same reason hooks use an absolute path."""
    return str(pathlib.Path(sys.executable).parent / MCP_COMMAND)


def _merge_json_mcp(
    settings: dict[str, object], host: str, store_root: pathlib.Path | None
) -> None:
    key = "mcp_servers" if host == moments.HOST_MUSE_CODE else "mcpServers"
    servers = settings.setdefault(key, {})
    if not isinstance(servers, dict):
        raise ValidationError([FieldError(f"settings.{key}", "must be an object")])
    expected: dict[str, object] = {
        "transport": "stdio",
        "command": mcp_binary(),
        "args": [],
    }
    if host == moments.HOST_MUSE_CODE:
        expected["mode"] = "optional"
    if store_root is not None:
        expected["env"] = {"AGENT_MEMORY_STORE": str(pathlib.Path(store_root).resolve())}
    existing = servers.get(MCP_SERVER)
    if existing is not None and existing != expected:
        raise ValidationError(
            [FieldError(f"settings.{key}.{MCP_SERVER}", "already exists with different values")]
        )
    servers[MCP_SERVER] = expected


def _install_external_mcp(
    host: str, target: pathlib.Path, store_root: pathlib.Path | None
) -> None:
    if host == moments.HOST_CLAUDE_CODE:
        home = target.parent.parent
        claude_config = home / ".claude.json"
        settings = _read_settings(claude_config)
        _merge_json_mcp(settings, host, store_root)
        rendered = json.dumps(settings, indent=SETTINGS_INDENT, sort_keys=True) + "\n"
        if not claude_config.exists() or claude_config.read_text(encoding="utf-8") != rendered:
            _atomic_write(claude_config, rendered)
        return
    if host != moments.HOST_CODEX:
        return
    binary = shutil.which(BINARIES[host])
    if binary is None:
        raise ValidationError([FieldError("mcp", "Codex binary is required to configure MCP")])
    environment = {**os.environ, "CODEX_HOME": str(target.parent)}
    command = [binary, "mcp", "add", MCP_SERVER]
    if store_root is not None:
        command += ["--env", f"AGENT_MEMORY_STORE={pathlib.Path(store_root).resolve()}"]
    command += ["--", mcp_binary()]
    current = subprocess.run(
        [binary, "mcp", "get", MCP_SERVER, "--json"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
        env=environment,
    )
    if current.returncode == 0:
        try:
            configured = json.loads(current.stdout)
        except json.JSONDecodeError:
            configured = {}
        rendered = json.dumps(configured)
        expected_store = str(pathlib.Path(store_root).resolve()) if store_root else ""
        if mcp_binary() in rendered and (not expected_store or expected_store in rendered):
            return
        raise ValidationError(
            [FieldError("mcp", f"{MCP_SERVER} already exists with different values")]
        )
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
        env=environment,
    )
    if completed.returncode != 0:
        detail = (completed.stderr.strip() or completed.stdout.strip()).splitlines()
        raise ValidationError(
            [FieldError("mcp", detail[-1] if detail else "Codex MCP configuration failed")]
        )


def _muse_data_home(environment: dict[str, str] | None = None) -> pathlib.Path:
    env = os.environ if environment is None else environment
    fallback = pathlib.Path(env.get("HOME", "~")).expanduser() / ".local" / "share"
    return pathlib.Path(env.get("XDG_DATA_HOME") or fallback)


def _install_skill(path: pathlib.Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = prompts.skill()
    if not path.exists() or path.read_text(encoding="utf-8") != rendered:
        path.write_text(rendered, encoding="utf-8")


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
