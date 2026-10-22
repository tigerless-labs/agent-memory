"""Fake native Host processes drive the real run-scoped Manage MCP adapter end to end."""

import json
import os
import pathlib
import sys

import pytest
from agent_memory.cli.main import main
from agent_memory.core import sessions
from agent_memory.core.config import OperationExecutorConfig
from agent_memory.core.errors import ReasonerUnavailableError, ValidationError
from agent_memory.core.manage import Manage
from agent_memory.core.manage_toolkit import TOOL_LIST, TOOL_READ, TOOL_SUBMIT
from agent_memory.core.store import Store
from agent_memory.executor import hosts
from agent_memory.executor.reasoners import ToolHostReasoner

FAKE_CODEX = """#!{python}
import json, os, subprocess, sys, tomllib

argv = sys.argv[1:]
def after(flag):
    return argv[argv.index(flag) + 1]

overrides = tomllib.loads("\\n".join(argv[i + 1] for i, part in enumerate(argv) if part == "-c"))
server = next(iter(overrides["mcp_servers"].values()))
prompt = sys.stdin.read()
system = open(overrides["model_instructions_file"], encoding="utf-8").read()
print(json.dumps({{"type": "thread.started", "thread_id": "fake"}}), flush=True)
child = subprocess.Popen(
    [server["command"], *server["args"]],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
)

def rpc(request_id, method, params=None):
    message = {{"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {{}}}}
    child.stdin.write(json.dumps(message) + "\\n")
    child.stdin.flush()
    return json.loads(child.stdout.readline())

rpc(0, "initialize")
listed = [tool["name"] for tool in rpc(1, "tools/list")["result"]["tools"]]
calls = []
print(json.dumps({{"type": "item.started", "item": {{
    "id": "menu", "type": "mcp_tool_call"
}}}}), flush=True)
menu_reply = rpc(2, "tools/call", {{"name": "list_proposals", "arguments": {{}}}})
print(json.dumps({{"type": "item.completed", "item": {{
    "id": "menu", "type": "mcp_tool_call"
}}}}), flush=True)
calls.append(menu_reply)
menu = json.loads(menu_reply["result"]["content"][0]["text"])
request_id = 3
for proposal in menu:
    for source in proposal["sources"]:
        reply = rpc(request_id, "tools/call", {{
            "name": "read_evidence",
            "arguments": {{"proposal": proposal["id"], "name": source["name"]}},
        }})
        calls.append(reply)
        request_id += 1
verdicts = [{{"proposal": proposal["id"], "verdict": "reject"}} for proposal in menu]
calls.append(rpc(request_id, "tools/call", {{
    "name": "submit_verdicts", "arguments": {{"verdicts": verdicts}},
}}))
child.stdin.close()
child.wait()

with open(os.environ["FAKE_MANAGE_LOG"], "w", encoding="utf-8") as handle:
    json.dump({{"argv": argv, "prompt": prompt, "system": system, "listed": listed,
               "calls": calls, "executor": os.environ.get("AGENT_MEMORY_EXECUTOR")}}, handle)
open(after("--output-last-message"), "w", encoding="utf-8").write("review submitted")
print(json.dumps({{"type": "turn.completed", "usage": {{
    "input_tokens": 900, "cached_input_tokens": 600, "output_tokens": 90,
}}}}))
"""


FAKE_MUSE = """#!{python}
import json, os, subprocess, sys, time

argv = sys.argv[1:]
def after(flag):
    return argv[argv.index(flag) + 1]

if "--version" in argv:
    print("Muse Code 1.4.9")
    raise SystemExit(0)

mode = os.environ.get("FAKE_MANAGE_MODE", "normal")
if mode == "timeout":
    time.sleep(10)
if mode == "exit":
    print("simulated Muse failure", file=sys.stderr)
    raise SystemExit(7)

settings_path = os.path.join(os.environ["XDG_CONFIG_HOME"], "muse", "settings.json")
settings = json.load(open(settings_path, encoding="utf-8"))
server = next(iter(settings["mcp_servers"].values()))
prompt = open(after("--prompt-file"), encoding="utf-8").read()
child = subprocess.Popen(
    [server["command"], *server["args"]],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
)

def rpc(request_id, method, params=None):
    message = {{"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {{}}}}
    child.stdin.write(json.dumps(message) + "\\n")
    child.stdin.flush()
    return json.loads(child.stdout.readline())

rpc(0, "initialize")
listed = [tool["name"] for tool in rpc(1, "tools/list")["result"]["tools"]]
calls = []
menu_reply = rpc(2, "tools/call", {{"name": "list_proposals", "arguments": {{}}}})
calls.append(menu_reply)
menu = json.loads(menu_reply["result"]["content"][0]["text"])
request_id = 3
if mode == "normal":
    calls.append(rpc(request_id, "tools/call", {{
        "name": "read_evidence",
        "arguments": {{"proposal": "not-in-this-run", "name": menu[0]["sources"][0]["name"]}},
    }}))
    request_id += 1
    calls.append(rpc(request_id, "tools/call", {{
        "name": "read_evidence",
        "arguments": {{"proposal": menu[0]["id"], "name": "not-a-target"}},
    }}))
    request_id += 1
    calls.append(rpc(request_id, "tools/call", {{
        "name": "read_evidence",
        "arguments": {{
            "proposal": menu[0]["id"],
            "name": menu[0]["sources"][0]["name"],
            "pointer": "sessions/../secret#0",
        }},
    }}))
    request_id += 1

if mode in ("normal", "raw"):
    for proposal in menu:
        for source in proposal["sources"]:
            calls.append(rpc(request_id, "tools/call", {{
                "name": "read_evidence",
                "arguments": {{"proposal": proposal["id"], "name": source["name"]}},
            }}))
            request_id += 1
            if mode == "raw" and source["provenance"]:
                calls.append(rpc(request_id, "tools/call", {{
                    "name": "read_evidence",
                    "arguments": {{
                        "proposal": proposal["id"],
                        "name": source["name"],
                        "pointer": source["provenance"][0],
                    }},
                }}))
                request_id += 1
    verdicts = [{{"proposal": proposal["id"], "verdict": "reject"}} for proposal in menu]
    calls.append(rpc(request_id, "tools/call", {{
        "name": "submit_verdicts", "arguments": {{"verdicts": verdicts}},
    }}))

child.stdin.close()
child.wait()
with open(os.environ["FAKE_MANAGE_LOG"], "w", encoding="utf-8") as handle:
    json.dump({{
        "argv": argv,
        "prompt": prompt,
        "listed": listed,
        "calls": calls,
        "executor": os.environ.get("AGENT_MEMORY_EXECUTOR"),
        "settings": settings,
    }}, handle)
print(json.dumps({{"kind": "run_terminal", "terminal": "completed", "text": "review submitted"}}))
"""


def _fake_codex(install, tmp_path):
    return install(tmp_path / "bin" / "codex", FAKE_CODEX.format(python=sys.executable))


def _fake_muse(install, tmp_path):
    return install(tmp_path / "bin" / "muse", FAKE_MUSE.format(python=sys.executable))


def _seed(store, *, provenance=False):
    first = store.archive.append_session(
        "drain-first-source",
        [{"role": "assistant", "text": "The first drain note was tentative."}],
    )
    second = store.archive.append_session(
        "drain-second-source",
        [{"role": "user", "text": "I confirmed staging uses a 20 second drain."}],
    )
    store.record(
        type="experience",
        name="drain-window-first",
        abstract="Queue drain timeout expires before the worker lease completes",
        body="The drain is 20 seconds and the worker lease is 30 seconds.",
        provenance=[sessions.render_pointer(first)] if provenance and first else [],
    )
    store.record(
        type="experience",
        name="drain-window-second",
        abstract="Queue drain timeout expires before the worker lease completes on staging",
        body="The staging drain is 20 seconds and the worker lease is 30 seconds.",
        provenance=[sessions.render_pointer(second)] if provenance and second else [],
    )


def test_mem_sleep_runs_native_codex_mcp_review_then_manage_validation(
    store, tmp_path, monkeypatch, capsys, python_executable
):
    _seed(store)
    store.config.executor.manage = OperationExecutorConfig(
        reasoner="host",
        host="codex",
        host_model="test-model",
        tool_mode="native",
        timeout_seconds=30.0,
    )
    store.config.save(store.root)
    log = tmp_path / "manage-host.json"
    binary = _fake_codex(python_executable, tmp_path)
    monkeypatch.setenv("PATH", str(binary.parent) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("FAKE_MANAGE_LOG", str(log))

    assert main(["--json", "--store", str(store.root), "sleep"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["review"]["mode"] == "native"
    assert payload["review"]["complete"] is True
    assert payload["review"]["tool_calls"] >= 3
    assert payload["review"]["agent_turns"] == 1
    assert payload["review"]["input_tokens"] == 900
    assert payload["review"]["cached_input_tokens"] == 600
    assert payload["review"]["output_tokens"] == 90
    assert payload["review"]["startup_seconds"] is not None
    assert payload["review"]["model_wait_seconds"] is not None
    assert payload["review"]["mcp_seconds"] is not None
    assert payload["review"]["shutdown_seconds"] is not None
    assert payload["review"]["apply_seconds"] >= 0.0
    assert payload["decisions"]
    assert all(decision["verdict"] == "rejected" for decision in payload["decisions"])

    trace = json.loads(log.read_text(encoding="utf-8"))
    assert set(trace["listed"]) == {TOOL_LIST, TOOL_READ, TOOL_SUBMIT}
    assert all(call["result"]["isError"] is False for call in trace["calls"])
    assert "submit_verdicts" in trace["system"]
    assert "The staging drain is 20 seconds" not in trace["prompt"]
    assert '"raw_session_evidence": false' in trace["prompt"]
    assert trace["executor"] == "1"
    assert "--ignore-user-config" in trace["argv"]
    assert trace["argv"][trace["argv"].index("--sandbox") + 1] == "read-only"
    assert any("memory_review" in part for part in trace["argv"])
    assert "analytics.enabled=false" in trace["argv"]

    reopened = Store(store.root, agent="assert")
    assert all(
        reopened.find(name).is_active() for name in ("drain-window-first", "drain-window-second")
    )
    assert not Manage(reopened).proposals()
    report = pathlib.Path(payload["path"]).read_text(encoding="utf-8")
    assert "list_proposals" in report
    assert "read_evidence" in report
    assert "submit_verdicts" in report


@pytest.mark.parametrize("raw_session_evidence", [False, True])
def test_mem_sleep_runs_native_muse_tools_with_scoped_evidence(
    store, tmp_path, monkeypatch, capsys, raw_session_evidence, python_executable
):
    _seed(store, provenance=True)
    store.config.manage.review_raw_session_evidence = raw_session_evidence
    store.config.executor.manage = OperationExecutorConfig(
        reasoner="host",
        host="muse-code",
        host_model="test-model",
        tool_mode="native",
        timeout_seconds=30.0,
    )
    store.config.save(store.root)
    log = tmp_path / "manage-muse.json"
    binary = _fake_muse(python_executable, tmp_path)
    monkeypatch.setenv("PATH", str(binary.parent) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("FAKE_MANAGE_LOG", str(log))
    monkeypatch.setenv("FAKE_MANAGE_MODE", "raw" if raw_session_evidence else "normal")

    assert main(["--json", "--store", str(store.root), "sleep"]) == 0
    payload = json.loads(capsys.readouterr().out)
    review = payload["review"]
    trace = json.loads(log.read_text(encoding="utf-8"))

    assert review["mode"] == "native"
    assert review["complete"] is True
    assert set(trace["listed"]) == {TOOL_LIST, TOOL_READ, TOOL_SUBMIT}
    assert trace["executor"] == "1"
    selected = json.loads(trace["argv"][trace["argv"].index("-c") + 1].removeprefix("run.toolset="))
    assert selected == [
        "mcp__memory_review__list_proposals",
        "mcp__memory_review__read_evidence",
        "mcp__memory_review__submit_verdicts",
    ]
    assert set(trace["settings"]["mcp_servers"]) == {"memory_review"}
    assert "--no-session-log" in trace["argv"]
    assert "--disable-shell" in trace["argv"]
    assert "--disable-write" in trace["argv"]
    assert ('"raw_session_evidence": true' in trace["prompt"]) is raw_session_evidence
    if raw_session_evidence:
        assert len(review["provenance_reads"]) >= 2
        assert all(call["result"]["isError"] is False for call in trace["calls"])
    else:
        assert review["provenance_reads"] == []
        assert [call["result"]["isError"] for call in trace["calls"][:4]] == [
            False,
            True,
            True,
            True,
        ]
    reopened = Store(store.root, agent="assert")
    assert all(
        reopened.find(name).is_active() for name in ("drain-window-first", "drain-window-second")
    )


@pytest.mark.parametrize(
    ("mode", "error_type", "match"),
    [
        ("incomplete", ValidationError, "submitted no complete verdict set"),
        ("exit", ReasonerUnavailableError, "simulated Muse failure"),
        ("timeout", ReasonerUnavailableError, "timeout"),
    ],
)
def test_native_muse_failure_modes_leave_store_unchanged(
    store, tmp_path, monkeypatch, mode, error_type, match, python_executable
):
    _seed(store)
    if mode == "timeout":
        store.config.executor.manage.timeout_seconds = 0.05
    before = {record.name: record.to_text() for record in store.records()}
    binary = _fake_muse(python_executable, tmp_path)
    monkeypatch.setenv("FAKE_MANAGE_LOG", str(tmp_path / "failure.json"))
    monkeypatch.setenv("FAKE_MANAGE_MODE", mode)
    reasoner = ToolHostReasoner(
        host=hosts.Host(
            hosts.HostSpec(
                name=hosts.HOST_MUSE_CODE,
                binary=str(binary),
                model="test-model",
                timeout_seconds=0.05 if mode == "timeout" else 5.0,
                attempts=1,
            )
        )
    )

    with pytest.raises(error_type, match=match):
        Manage(store).sleep(reasoner=reasoner)

    assert {record.name: record.to_text() for record in store.records()} == before
    assert not list(store.layout.dream_reports.glob("*.md"))
