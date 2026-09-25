"""Live Muse A/B/C compatibility probe using only disposable settings, workspace and Store."""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import tempfile

from agent_memory.core.store import Store

SENTINEL = "muse-sandbox-probe-7f31"
TIMEOUT_SECONDS = 240


def _run(
    command: list[str], environment: dict[str, str], cwd: pathlib.Path
) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        timeout=TIMEOUT_SECONDS,
        env=environment,
        cwd=cwd,
    )


def main() -> int:
    muse = shutil.which("muse")
    mem = shutil.which("mem")
    mem_hook = shutil.which("mem-hook")
    mem_mcp = shutil.which("mem-mcp")
    if not all((muse, mem, mem_hook, mem_mcp)):
        print(json.dumps({"ok": False, "error": "muse, mem, mem-hook and mem-mcp are required"}))
        return 2

    repository = pathlib.Path.cwd().resolve()
    parent_config = pathlib.Path(
        os.environ.get("XDG_CONFIG_HOME", pathlib.Path.home() / ".config")
    )
    auth_path = pathlib.Path(
        os.environ.get("MUSE_AUTH_PATH", parent_config / "muse" / "auth.json")
    )
    with tempfile.TemporaryDirectory(prefix=".muse-preflight-", dir=repository) as external_raw:
        external = pathlib.Path(external_raw)
        store_root = external / "store"
        workspace = external / "workspace"
        config_home = external / "config"
        data_home = external / "data"
        workspace.mkdir()
        config_home.joinpath("muse").mkdir(parents=True)
        data_home.mkdir()
        store = Store(store_root, agent="muse-preflight")
        store.init()
        store.record(abstract=SENTINEL, body=SENTINEL, type="fact", name="probe-seed")
        store.sync_index()

        settings = {
            "schema_version": 1,
            "hooks": {
                "Stop": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": (
                                    f"{mem_hook} --host muse-code --store {store_root}"
                                ),
                                "timeout": 30,
                            }
                        ],
                    }
                ]
            },
            "mcp_servers": {
                "agent-memory": {
                    "transport": "stdio",
                    "command": str(mem_mcp),
                    "args": [],
                    "env": {"AGENT_MEMORY_STORE": str(store_root)},
                    "mode": "required",
                }
            },
        }
        config_home.joinpath("muse", "settings.json").write_text(
            json.dumps(settings), encoding="utf-8"
        )
        environment = {
            **os.environ,
            "XDG_CONFIG_HOME": str(config_home),
            "XDG_DATA_HOME": str(data_home),
            "MUSE_AUTH_PATH": str(auth_path),
            "MUSE_NO_AUTO_UPDATE": "1",
            "AGENT_MEMORY_STORE": str(store_root),
        }

        version = _run([str(muse), "--version"], environment, workspace)
        hook = _run(
            [str(muse), "exec", "--provider", "echo", "--workspace", str(workspace), "hook"],
            environment,
            workspace,
        )
        hook_wrote = bool(list(store.layout.sessions.glob("*.jsonl")))

        recall_prompt = (
            f"Use the shell to run exactly: mem --json recall {SENTINEL}. "
            f"Reply with {SENTINEL} if the result contains it."
        )
        shell = _run(
            [str(muse), "exec", "--json", "--workspace", str(workspace), recall_prompt],
            environment,
            workspace,
        )
        shell_read = shell.returncode == 0 and SENTINEL in shell.stdout

        before = len(store.records())
        mcp_prompt = (
            "Call the memory_record MCP tool exactly once with type fact, "
            f"abstract {SENTINEL}-mcp, and body {SENTINEL}-mcp."
        )
        mcp = _run(
            [str(muse), "exec", "--json", "--workspace", str(workspace), mcp_prompt],
            environment,
            workspace,
        )
        records = store.records()
        mcp_wrote = mcp.returncode == 0 and any(
            record.abstract == f"{SENTINEL}-mcp" for record in records[before:]
        )
        result = {
            "ok": shell_read and hook.returncode == 0 and hook_wrote and mcp_wrote,
            "version": (version.stdout.strip() or version.stderr.strip()).splitlines()[:1],
            "shell_recall": shell_read,
            "hook_write": hook.returncode == 0 and hook_wrote,
            "mcp_write": mcp_wrote,
            "sandbox_disabled": False,
            "workspace_native_memory_present": False,
            "account_native_memory_isolation": "unverified",
        }
        print(json.dumps(result, sort_keys=True))
        return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
