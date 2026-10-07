"""Read-only host preflight with stable failure codes."""

from __future__ import annotations

import dataclasses
import json
import os
import pathlib
import subprocess
import tempfile
import tomllib

from agent_memory.core import prompts
from agent_memory.core.store import Store

from . import moments, openrouter, setup

READY = "READY"
FAILED = "FAILED"


@dataclasses.dataclass(frozen=True)
class Check:
    code: str
    ok: bool
    detail: str
    required: bool = True

    def as_dict(self) -> dict[str, object]:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class Report:
    host: str
    store: pathlib.Path
    settings: pathlib.Path
    checks: tuple[Check, ...]
    version: str = ""

    @property
    def status(self) -> str:
        return FAILED if any(not item.ok and item.required for item in self.checks) else READY

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "host": self.host,
            "version": self.version,
            "store": str(self.store),
            "settings": str(self.settings),
            "checks": [item.as_dict() for item in self.checks],
        }


def run(
    store: Store,
    host: str,
    *,
    settings_path: pathlib.Path | None = None,
    provider: str | None = None,
    model: str | None = None,
    mcp: bool = False,
    live: bool = True,
    environment: dict[str, str] | None = None,
) -> Report:
    host = setup.canonical_host(host)
    target = settings_path or setup.default_settings_path(host, environment)
    checks: list[Check] = []
    version = ""
    try:
        version = setup.probe(host)
        checks.append(Check("HOST_BINARY_OK", True, version))
    except Exception as error:
        checks.append(Check("HOST_BINARY_MISSING", False, str(error)))
    checks.extend(_store_checks(store))
    configured = _settings(target, checks)
    if configured is not None:
        checks.extend(_hook_checks(configured, host, store.root))
    skill = setup.skill_path(host, target)
    skill_ok = skill.is_file() and skill.read_text(encoding="utf-8") == prompts.skill()
    checks.append(
        Check(
            "SKILL_OK" if skill_ok else "SKILL_INVALID",
            skill_ok,
            f"installed at {skill}" if skill.is_file() else f"missing at {skill}",
        )
    )
    checks.extend(_reasoner_checks(store, host))
    if not (host == moments.HOST_MUSE_CODE and provider):
        checks.append(
            _live_reasoner_check(store, host)
            if live
            else Check(
                "LIVE_PREFLIGHT_SKIPPED",
                False,
                "live host reasoner check was explicitly skipped",
            )
        )
    if mcp:
        checks.append(_mcp_check(host, target, store.root, configured, environment))
    if host == moments.HOST_CODEX:
        checks.extend(_codex_checks(target, store.root))
    if host == moments.HOST_MUSE_CODE and provider:
        checks.extend(
            _muse_provider_checks(
                configured,
                provider=provider,
                model=model,
                live=live,
                environment=environment,
            )
        )
    return Report(
        host=host, store=store.root, settings=target, checks=tuple(checks), version=version
    )


def _store_checks(store: Store) -> list[Check]:
    initialized = (
        store.root.is_dir()
        and store.layout.schemas_dir.is_dir()
        and (store.root / "config.toml").is_file()
    )
    checks = [
        Check(
            "STORE_INITIALIZED" if initialized else "STORE_NOT_INITIALIZED",
            initialized,
            str(store.root),
        )
    ]
    writable = False
    detail = str(store.root)
    if initialized:
        try:
            descriptor, temporary = tempfile.mkstemp(prefix=".doctor-", dir=store.layout.state_dir)
            os.close(descriptor)
            pathlib.Path(temporary).unlink()
            writable = True
        except OSError as error:
            detail = f"{store.root}: {error}"
    checks.append(
        Check("STORE_WRITABLE" if writable else "STORE_NOT_WRITABLE", writable, detail)
    )
    return checks


def _settings(target: pathlib.Path, checks: list[Check]) -> dict[str, object] | None:
    if not target.is_file():
        checks.append(Check("HOST_CONFIG_INVALID", False, f"missing {target}"))
        return None
    try:
        parsed = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        checks.append(Check("HOST_CONFIG_INVALID", False, f"{target}: {error}"))
        return None
    if not isinstance(parsed, dict):
        checks.append(Check("HOST_CONFIG_INVALID", False, f"{target} is not a JSON object"))
        return None
    checks.append(Check("HOST_CONFIG_OK", True, str(target)))
    return parsed


def _hook_checks(
    configured: dict[str, object], host: str, store_root: pathlib.Path
) -> list[Check]:
    hooks = configured.get(setup.HOOKS_KEY)
    if not isinstance(hooks, dict):
        return [Check("HOOK_INVALID", False, "settings.hooks is missing or not an object")]
    expected_store = str(store_root.resolve())
    failures = []
    for event in moments.DIALECTS[host]:
        entries = hooks.get(event)
        if not isinstance(entries, list):
            failures.append(f"{event} missing")
            continue
        managed = [entry for entry in entries if setup.HOOK_COMMAND in json.dumps(entry)]
        if len(managed) != 1:
            failures.append(f"{event} has {len(managed)} managed hooks")
            continue
        if expected_store not in json.dumps(managed[0]):
            failures.append(f"{event} does not pin Store {expected_store}")
    return [
        Check(
            "HOOK_OK" if not failures else "HOOK_INVALID",
            not failures,
            "all lifecycle hooks installed once" if not failures else "; ".join(failures),
        )
    ]


def _reasoner_checks(store: Store, host: str) -> list[Check]:
    executor = store.config.executor
    if executor.reasoner == "endpoint":
        ok = bool(executor.endpoint)
        detail = executor.endpoint or "executor.reasoner=endpoint but executor.endpoint is empty"
    else:
        ok = bool(setup.BINARIES.get(host))
        detail = f"boundary distillation uses {host}"
    return [Check("REASONER_AVAILABLE" if ok else "REASONER_UNAVAILABLE", ok, detail)]


def _live_reasoner_check(store: Store, host: str) -> Check:
    """Exercise the same executor used by boundary distillation, with one bounded attempt."""
    try:
        from agent_memory.executor.distiller import distiller
        from agent_memory.executor.reasoners import HostReasoner

        executor = store.config.executor
        if executor.reasoner == "endpoint":
            reasoner = distiller(executor)
        else:
            reasoner = HostReasoner.for_host(host, model=executor.host_model)
            reasoner.host.spec = dataclasses.replace(
                reasoner.host.spec,
                attempts=1,
                timeout_seconds=min(executor.timeout_seconds, 60.0),
            )
        reply = reasoner("Reply with exactly AGENT_MEMORY_READY.")
    except Exception as error:
        return Check(
            "REASONER_UNAVAILABLE",
            False,
            f"live reasoner probe failed: {type(error).__name__}",
        )
    ok = "AGENT_MEMORY_READY" in reply
    return Check(
        "REASONER_LIVE_OK" if ok else "REASONER_UNAVAILABLE",
        ok,
        "boundary reasoner completed a live request" if ok else "live reasoner returned no READY",
    )


def _mcp_check(
    host: str,
    target: pathlib.Path,
    store_root: pathlib.Path,
    configured: dict[str, object] | None,
    environment: dict[str, str] | None,
) -> Check:
    if host == moments.HOST_CODEX:
        binary = setup.BINARIES[host]
        env = {
            **(os.environ if environment is None else environment),
            "CODEX_HOME": str(target.parent),
        }
        try:
            result = subprocess.run(
                [binary, "mcp", "get", setup.MCP_SERVER, "--json"],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
                env=env,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            return Check("MCP_INVALID", False, str(error))
        rendered = result.stdout + result.stderr
        ok = (
            result.returncode == 0
            and setup.mcp_binary() in rendered
            and str(store_root) in rendered
        )
        return Check("MCP_OK" if ok else "MCP_INVALID", ok, "Codex MCP server configuration")
    if host == moments.HOST_CLAUDE_CODE:
        path = target.parent.parent / ".claude.json"
        try:
            configured = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            configured = None
        key = "mcpServers"
    else:
        key = "mcp_servers"
    servers = configured.get(key) if isinstance(configured, dict) else None
    server = servers.get(setup.MCP_SERVER) if isinstance(servers, dict) else None
    rendered = json.dumps(server) if server is not None else ""
    ok = setup.mcp_binary() in rendered and str(store_root.resolve()) in rendered
    return Check("MCP_OK" if ok else "MCP_INVALID", ok, f"{setup.MCP_SERVER} stdio server")


def _codex_checks(target: pathlib.Path, store_root: pathlib.Path) -> list[Check]:
    config = target.parent / "config.toml"
    checks: list[Check] = []
    if config.is_file():
        try:
            parsed = tomllib.loads(config.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as error:
            return [Check("HOST_CONFIG_INVALID", False, f"{config}: {error}")]
        features = parsed.get("features", {})
        enabled = not isinstance(features, dict) or features.get("hooks", True) is not False
        checks.append(
            Check(
                "CODEX_HOOKS_ENABLED" if enabled else "HOOK_INVALID",
                enabled,
                "Codex hooks feature enabled" if enabled else "features.hooks=false",
            )
        )
        sandbox = parsed.get("sandbox_mode", "")
        if sandbox == "read-only":
            checks.append(
                Check(
                    "CODEX_SANDBOX_STORE_ACCESS",
                    False,
                    f"default sandbox is read-only; Store writes require access to {store_root}",
                    required=False,
                )
            )
        workspace = parsed.get("sandbox_workspace_write", {})
        raw_roots = workspace.get("writable_roots", []) if isinstance(workspace, dict) else []
        roots = raw_roots if isinstance(raw_roots, list) else []
        resolved_store = store_root.resolve()
        store_allowed = any(
            isinstance(root, str)
            and resolved_store.is_relative_to(pathlib.Path(root).expanduser().resolve())
            for root in roots
        )
        checks.append(
            Check(
                "CODEX_STORE_ACCESS_CONFIGURED"
                if store_allowed
                else "CODEX_STORE_ACCESS_REVIEW",
                store_allowed,
                (
                    f"workspace-write includes Store {resolved_store}"
                    if store_allowed
                    else (
                        f"agent commands that query Store {resolved_store} need --add-dir "
                        "or sandbox_workspace_write.writable_roots; setup does not expand "
                        "sandbox permissions automatically"
                    )
                ),
                required=False,
            )
        )
    checks.append(
        Check(
            "CODEX_HOOK_TRUST_REVIEW",
            False,
            "Codex may require one-time review of this non-managed user hook",
            required=False,
        )
    )
    return checks


def _muse_provider_checks(
    configured: dict[str, object] | None,
    *,
    provider: str,
    model: str | None,
    live: bool,
    environment: dict[str, str] | None,
) -> list[Check]:
    if provider != openrouter.PROVIDER:
        return [Check("HOST_CONFIG_INVALID", False, f"unsupported provider {provider!r}")]
    target = model or openrouter.DEFAULT_MODEL
    expected_model = target.removeprefix("meta/")
    routing_ok = bool(
        configured
        and configured.get("provider") == openrouter.MUSE_PROVIDER
        and configured.get("model") == expected_model
        and configured.get("endpoint_transport")
        == {"base_url": openrouter.DEFAULT_PROXY_URL, "auth": "bearer"}
    )
    checks = [
        Check(
            "PROVIDER_ROUTING_OK" if routing_ok else "HOST_CONFIG_INVALID",
            routing_ok,
            "Muse meta transport routes through the local OpenRouter bridge",
        )
    ]
    credential = openrouter.detect_credential(environment)
    checks.append(
        Check(
            "OPENROUTER_CREDENTIAL_OK" if credential else "OPENROUTER_CREDENTIAL_MISSING",
            credential is not None,
            (
                f"detected from {credential.source}"
                if credential
                else "set OPENROUTER_API_KEY or use muse auth"
            ),
        )
    )
    proxy_ok = openrouter.proxy_health(environment=environment)
    checks.append(
        Check(
            "PROXY_REACHABLE" if proxy_ok else "PROXY_UNREACHABLE",
            proxy_ok,
            openrouter.DEFAULT_PROXY_URL,
        )
    )
    if credential and live:
        code, detail = openrouter.openrouter_preflight(
            credential, model=target, environment=environment
        )
        checks.append(Check(code or "OPENROUTER_OK", code is None, detail))
        if code is None and proxy_ok:
            live_code, live_detail = openrouter.muse_live_preflight(
                credential, model=target, environment=environment
            )
            checks.append(Check(live_code or "MUSE_LIVE_OK", live_code is None, live_detail))
    elif not live:
        checks.append(
            Check(
                "LIVE_PREFLIGHT_SKIPPED",
                False,
                "live OpenRouter and Muse checks were explicitly skipped",
            )
        )
    return checks
