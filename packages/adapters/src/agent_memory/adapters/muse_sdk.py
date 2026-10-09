"""Safe bootstrap for SDK-owned Muse backends."""

from __future__ import annotations

import os
import pathlib
import re
import shutil
import signal
import subprocess
import sys

from agent_memory.core.config import MUSE_LAUNCHER_ENV_VAR, STORE_ENV_VAR
from agent_memory.core.store import Store

from . import doctor, moments, openrouter, setup

MINIMUM_NODE_MAJOR = 20
LIVE_TIMEOUT_SECONDS = 90
SHUTDOWN_GRACE_SECONDS = 5
VERSION_PATTERN = re.compile(r"(?<!\d)(\d+)\.(\d+)\.(\d+)(?!\d)")
SDK_PACKAGE = "@muse-code/sdk"


def run(
    store: Store,
    *,
    provider: str,
    model: str | None = None,
    live: bool = True,
    environment: dict[str, str] | None = None,
    cwd: pathlib.Path | None = None,
) -> dict[str, object]:
    env = dict(os.environ if environment is None else environment)
    selected_model = model or openrouter.DEFAULT_MODEL
    checks: list[doctor.Check] = []
    cli_version = ""
    try:
        cli_version = setup.probe(moments.HOST_MUSE_CODE)
        checks.append(doctor.Check("HOST_BINARY_OK", True, cli_version))
    except Exception as error:
        checks.append(doctor.Check("HOST_BINARY_MISSING", False, str(error)))

    try:
        store.init()
        checks.extend(doctor._store_checks(store))
    except OSError as error:
        checks.append(doctor.Check("STORE_NOT_WRITABLE", False, str(error)))

    launcher = _launcher_path(env)
    checks.append(
        doctor.Check(
            "SDK_LAUNCHER_OK" if launcher else "SDK_LAUNCHER_MISSING",
            launcher is not None,
            str(launcher) if launcher else "reinstall agent-memory so `mem-muse` is available",
        )
    )

    node_version = _node_version(env)
    if node_version is None:
        checks.append(doctor.Check("NODE_MISSING", False, "install Node 20 or newer"))
    else:
        node_semver = _semver(node_version)
        supported = node_semver is not None and node_semver[0] >= MINIMUM_NODE_MAJOR
        checks.append(
            doctor.Check(
                "NODE_VERSION_OK" if supported else "NODE_VERSION_UNSUPPORTED",
                supported,
                (
                    f"Node {node_version}"
                    if supported
                    else f"Node {node_version}; install Node 20 or newer"
                ),
            )
        )

    project_root = pathlib.Path.cwd() if cwd is None else cwd
    sdk_version = _sdk_version(env, project_root)
    if sdk_version is None:
        checks.append(
            doctor.Check(
                "SDK_PACKAGE_MISSING",
                False,
                f"run `{_sdk_install_command(cli_version)}` in the SDK application",
            )
        )
    else:
        checks.append(doctor.Check("SDK_PACKAGE_OK", True, f"{SDK_PACKAGE} {sdk_version}"))
        checks.append(_version_check(cli_version, sdk_version))

    credential = openrouter.detect_credential(env)
    if credential is None:
        checks.append(
            doctor.Check(
                "OPENROUTER_CREDENTIAL_MISSING",
                False,
                "set OPENROUTER_API_KEY in both bootstrap and application environments, "
                "or provision Muse auth",
            )
        )
    else:
        checks.append(
            doctor.Check("OPENROUTER_CREDENTIAL_OK", True, f"source: {credential.source}")
        )

    mcp = pathlib.Path(setup.mcp_binary())
    mcp_ready = mcp.is_file() and os.access(mcp, os.X_OK)
    checks.append(
        doctor.Check(
            "MCP_AUTO_ENABLED" if mcp_ready else "MCP_NOT_INSTALLED",
            mcp_ready,
            (
                f"managed sessions automatically use {mcp}"
                if mcp_ready
                else "optional mem-mcp executable is not installed"
            ),
            required=False,
        )
    )

    if _required_checks_pass(checks):
        if live and launcher is not None and credential is not None:
            checks.append(
                _live_preflight(launcher, store, credential, selected_model, env)
            )
        else:
            checks.append(
                doctor.Check(
                    "SDK_LIVE_PREFLIGHT_SKIPPED",
                    False,
                    "live managed request was explicitly skipped",
                )
            )

    status = doctor.READY if _required_checks_pass(checks) else doctor.FAILED
    contract = {
        "museBin": str(launcher.resolve()) if launcher else "",
        "args": ["serve"],
        "model": selected_model,
        "credential_source": credential.source if credential else "missing",
        "environment": [STORE_ENV_VAR, "OPENROUTER_API_KEY"],
    }
    return {
        "status": status,
        "host": moments.HOST_MUSE_CODE,
        "version": cli_version,
        "store": str(store.root),
        "mode": "sdk-managed",
        "provider": provider,
        "checks": [check.as_dict() for check in checks],
        "sdk": contract,
    }


def _launcher_path(environment: dict[str, str]) -> pathlib.Path | None:
    explicit = environment.get(MUSE_LAUNCHER_ENV_VAR, "").strip()
    candidate = (
        pathlib.Path(explicit)
        if explicit
        else pathlib.Path(sys.executable).parent / "mem-muse"
    )
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return candidate.resolve()
    discovered = shutil.which("mem-muse", path=environment.get("PATH"))
    return pathlib.Path(discovered).resolve() if discovered else None


def _node_version(environment: dict[str, str]) -> str | None:
    binary = shutil.which("node", path=environment.get("PATH"))
    if not binary:
        return None
    try:
        completed = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    rendered = (completed.stdout.strip() or completed.stderr.strip()).removeprefix("v")
    return rendered or None


def _sdk_version(environment: dict[str, str], cwd: pathlib.Path) -> str | None:
    binary = shutil.which("node", path=environment.get("PATH"))
    if not binary:
        return None
    script = (
        "const fs=require('node:fs'),path=require('node:path');"
        "let d=path.dirname(require.resolve('@muse-code/sdk'));"
        "for(;;){const p=path.join(d,'package.json');"
        "if(fs.existsSync(p)){const x=JSON.parse(fs.readFileSync(p,'utf8'));"
        "if(x.name==='@muse-code/sdk'){process.stdout.write(x.version);break;}}"
        "const n=path.dirname(d);if(n===d)process.exit(2);d=n;}"
    )
    try:
        completed = subprocess.run(
            [binary, "-e", script],
            cwd=cwd,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    version = completed.stdout.strip()
    return version if completed.returncode == 0 and _semver(version) else None


def _version_check(cli_version: str, sdk_version: str) -> doctor.Check:
    cli = _semver(cli_version)
    sdk = _semver(sdk_version)
    if cli is None or sdk is None:
        return doctor.Check(
            "SDK_VERSION_UNKNOWN",
            False,
            f"could not compare Muse CLI {cli_version!r} with SDK {sdk_version!r}",
        )
    if cli == sdk:
        return doctor.Check("SDK_VERSION_OK", True, f"Muse CLI and SDK both use {sdk_version}")
    if cli[:2] == sdk[:2]:
        return doctor.Check(
            "SDK_VERSION_SKEW",
            False,
            f"Muse CLI {'.'.join(map(str, cli))} and SDK {sdk_version} differ by patch version",
            required=False,
        )
    return doctor.Check(
        "SDK_VERSION_INCOMPATIBLE",
        False,
        f"Muse CLI {'.'.join(map(str, cli))} requires a matching {SDK_PACKAGE} version",
    )


def _live_preflight(
    launcher: pathlib.Path,
    store: Store,
    credential: openrouter.Credential,
    model: str,
    environment: dict[str, str],
) -> doctor.Check:
    env = {**environment, STORE_ENV_VAR: str(store.root)}
    command = [
        str(launcher),
        "exec",
        "--model",
        model,
        "--no-session-log",
        "--disable-shell",
        "Reply with exactly READY.",
    ]
    try:
        process = subprocess.Popen(
            command,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        stdout, stderr = process.communicate(timeout=LIVE_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        _stop_process_group(process)
        return doctor.Check(
            "SDK_LIVE_UNAVAILABLE", False, "managed launcher live request timed out"
        )
    except OSError as error:
        return doctor.Check("SDK_LIVE_UNAVAILABLE", False, str(error))
    output = openrouter.redact(stdout + stderr, credential.value).strip()
    if process.returncode == 0 and "READY" in output:
        return doctor.Check(
            "SDK_LIVE_OK", True, "managed launcher completed a live OpenRouter request"
        )
    detail = output.splitlines()[-1] if output else f"exit {process.returncode}"
    return doctor.Check("SDK_LIVE_UNAVAILABLE", False, detail)


def _stop_process_group(process: subprocess.Popen[str]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except OSError:
        process.terminate()
    try:
        process.communicate(timeout=SHUTDOWN_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            process.kill()
        process.communicate()


def _semver(value: str) -> tuple[int, int, int] | None:
    match = VERSION_PATTERN.search(value)
    if match is None:
        return None
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch)


def _sdk_install_command(cli_version: str) -> str:
    version = _semver(cli_version)
    suffix = f"@{'.'.join(map(str, version))}" if version else ""
    return f"npm install {SDK_PACKAGE}{suffix}"


def _required_checks_pass(checks: list[doctor.Check]) -> bool:
    return all(check.ok or not check.required for check in checks)
