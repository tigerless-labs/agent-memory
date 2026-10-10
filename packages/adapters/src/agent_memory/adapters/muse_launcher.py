"""Managed Muse SDK backend with isolated agent-memory and OpenRouter wiring."""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
from collections.abc import Sequence
from contextlib import suppress
from types import FrameType
from typing import Any, cast

from agent_memory.core.config import (
    EXECUTOR_ENV_VAR,
    MUSE_BINARY_ENV_VAR,
    MUSE_SETTINGS_ENV_VAR,
    STORE_ENV_VAR,
)
from agent_memory.core.errors import ValidationError
from agent_memory.core.store import Store

from . import moments, openrouter, setup
from .openrouter_bridge import OpenRouterBridge

EXIT_OK = 0
EXIT_RUNTIME = 1
EXIT_CONFIGURATION = 2
MANAGED_COMMANDS = frozenset({"serve", "exec"})
RUNTIME_DIRNAME = "muse-sdk"


def run(
    argv: Sequence[str] | None = None,
    *,
    environment: dict[str, str] | None = None,
) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    env = dict(os.environ if environment is None else environment)
    binary = _real_muse(env)
    if binary is None:
        return _error("HOST_BINARY_MISSING", "set AGENT_MEMORY_MUSE_BINARY or put muse on PATH")
    if not args or args[0] not in MANAGED_COMMANDS:
        return _passthrough(binary, args, env)
    credential = openrouter.detect_credential(env)
    if credential is None:
        return _error(
            "OPENROUTER_CREDENTIAL_MISSING",
            "set OPENROUTER_API_KEY or store an OpenRouter key with muse auth",
        )
    model = _model(args)
    try:
        store = Store(env.get(STORE_ENV_VAR))
        store.init()
        with OpenRouterBridge(credential, model) as bridge:
            return _managed_run(binary, args, env, store, credential, model, bridge.base_url)
    except (OSError, ValidationError, ValueError) as error:
        return _error("MUSE_BACKEND_START_FAILED", openrouter.redact(str(error), credential.value))


def main() -> int:
    return run()


def _managed_run(
    binary: str,
    args: list[str],
    environment: dict[str, str],
    store: Store,
    credential: openrouter.Credential,
    model: str,
    bridge_url: str,
) -> int:
    runtime_root = _state_home(environment) / "agent-memory" / RUNTIME_DIRNAME
    runtime_root.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix=f"{os.getpid()}-", dir=runtime_root) as temporary:
            runtime = pathlib.Path(temporary)
            config_home = runtime / "config"
            settings_path = config_home / "muse" / "settings.json"
            auth_path = settings_path.with_name("auth.json")
            _write_auth(auth_path, credential)
            mcp = pathlib.Path(setup.mcp_binary())
            is_executor = bool(environment.get(EXECUTOR_ENV_VAR))
            setup.install(
                moments.HOST_MUSE_CODE,
                settings_path,
                store.root,
                provider=openrouter.PROVIDER,
                model=model,
                provider_url=bridge_url,
                muse_launcher=pathlib.Path(sys.executable).parent / "mem-muse",
                muse_binary=pathlib.Path(binary),
                mcp=mcp.is_file() and os.access(mcp, os.X_OK) and not is_executor,
                lifecycle=not is_executor,
            )
            child_env = {
                **environment,
                "XDG_CONFIG_HOME": str(config_home),
                "MUSE_AUTH_PATH": str(auth_path),
                "MUSE_NO_AUTO_UPDATE": "1",
                MUSE_SETTINGS_ENV_VAR: str(settings_path),
                STORE_ENV_VAR: str(store.root),
                MUSE_BINARY_ENV_VAR: binary,
            }
            process = subprocess.Popen([binary, *args], env=child_env)
            return _wait(process)
    finally:
        with suppress(OSError):
            runtime_root.rmdir()


def _real_muse(environment: dict[str, str]) -> str | None:
    explicit = environment.get(MUSE_BINARY_ENV_VAR, "").strip()
    candidate = explicit or shutil.which("muse", path=environment.get("PATH"))
    if not candidate:
        return None
    path = pathlib.Path(candidate).expanduser()
    return str(path.resolve()) if path.is_file() and os.access(path, os.X_OK) else None


def _model(args: list[str]) -> str:
    selected = openrouter.DEFAULT_MODEL
    for index, value in enumerate(args):
        if value == "--model" and index + 1 < len(args):
            selected = args[index + 1]
        elif value.startswith("--model="):
            selected = value.partition("=")[2]
    return selected if "/" in selected else f"{openrouter.MUSE_PROVIDER}/{selected}"


def _write_auth(path: pathlib.Path, credential: openrouter.Credential) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "providers": {openrouter.MUSE_PROVIDER: {"api_key": credential.value}},
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)


def _wait(process: subprocess.Popen[bytes]) -> int:
    if threading.current_thread() is not threading.main_thread():
        return process.wait()
    previous: dict[signal.Signals, object] = {}

    def forward(signum: int, _frame: FrameType | None) -> None:
        if process.poll() is None:
            process.send_signal(signum)

    for selected in (signal.SIGINT, signal.SIGTERM):
        previous[selected] = signal.getsignal(selected)
        signal.signal(selected, forward)
    try:
        return process.wait()
    finally:
        for selected, handler in previous.items():
            signal.signal(selected, cast(Any, handler))


def _passthrough(binary: str, args: list[str], environment: dict[str, str]) -> int:
    try:
        return subprocess.run([binary, *args], env=environment, check=False).returncode
    except OSError as error:
        return _error("MUSE_START_FAILED", str(error))


def _state_home(environment: dict[str, str]) -> pathlib.Path:
    home = pathlib.Path(environment.get("HOME", "~")).expanduser()
    return pathlib.Path(environment.get("XDG_STATE_HOME") or home / ".local" / "state")


def _error(code: str, detail: str) -> int:
    print(f"mem-muse: {code}: {detail}", file=sys.stderr)
    return EXIT_CONFIGURATION if code.endswith("MISSING") else EXIT_RUNTIME


if __name__ == "__main__":
    raise SystemExit(main())
