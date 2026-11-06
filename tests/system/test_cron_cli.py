"""CLI-level crontab install/status/remove without touching the user's real crontab."""

from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from agent_memory.adapters import capture, cron_schedule
from agent_memory.cli.main import EXIT_OK, main
from agent_memory.core import dreaming
from agent_memory.core.config import OperationExecutorConfig
from agent_memory.core.ledger import LEDGER_FILENAME
from agent_memory.core.store import Store
from agent_memory.core.watermark import Watermark

POSIX_CRON = pytest.mark.skipif(os.name == "nt", reason="cron scheduling is POSIX-only")

FAKE_CRONTAB = """#!/bin/sh
set -eu
if [ "$1" = "-l" ]; then
  if [ -f "$FAKE_CRONTAB_FILE" ]; then
    cat "$FAKE_CRONTAB_FILE"
    exit 0
  fi
  echo "no crontab for test" >&2
  exit 1
fi
if [ "$1" = "-" ]; then
  cat > "$FAKE_CRONTAB_FILE"
  exit 0
fi
exit 2
"""


@POSIX_CRON
def test_cli_manages_one_store_block_and_preserves_unrelated_jobs(tmp_path, monkeypatch, capsys):
    store = tmp_path / "Store With Spaces"
    crontab_file = tmp_path / "user.crontab"
    crontab_file.write_text("11 2 * * * /usr/bin/unrelated\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    crontab = bin_dir / "crontab"
    crontab.write_text(FAKE_CRONTAB, encoding="utf-8")
    crontab.chmod(0o755)
    mem = bin_dir / "mem"
    mem.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    mem.chmod(0o755)
    environment = tmp_path / "reasoner.env"
    environment.write_text("HTTPS_PROXY=https://example.test\n", encoding="utf-8")
    environment.chmod(0o600)
    monkeypatch.setenv("FAKE_CRONTAB_FILE", str(crontab_file))
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ.get('PATH', '')}")
    monkeypatch.setattr(
        "agent_memory.adapters.cron_schedule._scheduler_running", lambda: True
    )
    monkeypatch.setattr("agent_memory.adapters.cron_schedule._is_wsl", lambda: False)

    def run(*args):
        assert main(["--store", str(store), "--json", "cron", *args]) == EXIT_OK
        return json.loads(capsys.readouterr().out)

    assert main(["--store", str(store), "--json", "init"]) == EXIT_OK
    capsys.readouterr()
    installed = run(
        "install",
        "--interval-minutes",
        "15",
        "--mem-path",
        str(mem),
        "--env-file",
        str(environment),
    )
    unchanged = run(
        "install",
        "--interval-minutes",
        "15",
        "--mem-path",
        str(mem),
        "--env-file",
        str(environment),
    )
    current = run("status")
    removed = run("remove")

    assert installed["status"] == "installed"
    assert unchanged["status"] == "unchanged"
    assert current["installed"] is True
    assert current["entry"].startswith("*/15 * * * * ")
    assert "--json sleep --if-due --trigger-source cron" in current["entry"]
    assert str(environment) in current["entry"]
    assert removed["status"] == "removed"
    assert crontab_file.read_text("utf-8") == "11 2 * * * /usr/bin/unrelated\n"


@POSIX_CRON
def test_generated_cron_command_completes_endpoint_dream_in_an_independent_process(
    tmp_path, monkeypatch
):
    """Close the cron acceptance gap without depending on an external model service."""
    requests = []

    class ReasonerHandler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802 - inherited HTTP handler API
            size = int(self.headers["Content-Length"])
            request = json.loads(self.rfile.read(size))
            prompt = request["messages"][0]["content"]
            proposal = re.search(r"^- (\S+) \(", prompt, flags=re.MULTILINE)
            requests.append(
                {
                    "path": self.path,
                    "authorization": self.headers.get("Authorization"),
                    "proposal": proposal.group(1) if proposal else "",
                }
            )
            verdict = json.dumps(
                {
                    "proposal": requests[-1]["proposal"],
                    "verdict": "reject",
                    "text": "retained by cron endpoint acceptance",
                }
            )
            response = json.dumps(
                {"choices": [{"message": {"content": verdict}}]}
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, _format, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), ReasonerHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    try:
        store = Store(tmp_path / "Store With Spaces")
        store.config.manage.trigger_min_sessions = 1
        store.config.manage.git_commit = False
        store.config.executor.manage = OperationExecutorConfig(
            reasoner="endpoint", model="acceptance-model"
        )
        store.init()
        store.record(
            type="fact",
            fields={"subject": "cron acceptance"},
            abstract="Nobody asks about this",
            weight=store.config.weight.floor,
        )
        capture.capture(
            store,
            "settled-session",
            ["user: remember cron acceptance", "assistant: noted"],
            source="pause",
        )
        mark = Watermark(store.layout).read("settled-session")
        Watermark(store.layout).settle("settled-session", mark.consumed)

        environment = tmp_path / "reasoner.env"
        environment.write_text(
            "\n".join(
                (
                    f"GEMINI_BASE_URL=http://127.0.0.1:{server.server_port}/v1",
                    "GEMINI_API_KEY=cron-secret",
                    "",
                )
            ),
            encoding="utf-8",
        )
        environment.chmod(0o600)
        log = tmp_path / "cron.log"
        crontab = {"text": ""}
        monkeypatch.setattr(cron_schedule, "_require_crontab", lambda: "/usr/bin/crontab")
        monkeypatch.setattr(cron_schedule, "_read_crontab", lambda _binary: crontab["text"])
        monkeypatch.setattr(
            cron_schedule,
            "_write_crontab",
            lambda _binary, content: crontab.__setitem__("text", content),
        )
        monkeypatch.setattr(cron_schedule, "_scheduler_running", lambda: True)
        monkeypatch.setattr(cron_schedule, "_is_wsl", lambda: False)
        monkeypatch.delenv("GEMINI_BASE_URL", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        mem = pathlib.Path(sys.executable).parent / "mem"
        installed = cron_schedule.install(
            store,
            mem_path=str(mem),
            log_path=str(log),
            env_file=str(environment),
        )
        completed = subprocess.run(
            str(installed["command"]),
            shell=True,
            executable="/bin/sh",
            check=False,
        )

        assert completed.returncode == 0
        output = json.loads(log.read_text("utf-8"))
        assert output["slept"] is True
        assert output["status"] == "succeeded"
        assert output["trigger_source"] == "cron"
        assert output["reasoner"] == {"kind": "endpoint", "model": "acceptance-model"}
        assert len(output["decisions"]) == 1
        assert requests == [
            {
                "path": "/v1/chat/completions",
                "authorization": "Bearer cron-secret",
                "proposal": output["decisions"][0]["proposal"],
            }
        ]
        assert pathlib.Path(output["path"]).is_file()
        assert (store.layout.dream_reports / LEDGER_FILENAME).is_file()
        state = dreaming.state(Store(store.root))
        assert state["status"] == dreaming.STATUS_SUCCEEDED
        assert state["last_report"] == output["path"]
        assert "cron-secret" not in str(installed["command"])
        assert "cron-secret" not in log.read_text("utf-8")
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)
