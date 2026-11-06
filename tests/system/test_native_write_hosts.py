"""End to end and offline: a fake host CLI starts the configured MCP adapter and drives it."""

import json
import os
import pathlib
import sys

import pytest
from agent_memory.core import distill, sessions, toolkit
from agent_memory.core.config import ExecutorConfig
from agent_memory.core.errors import ValidationError
from agent_memory.core.watermark import Watermark
from agent_memory.executor import distiller as executor_distiller
from agent_memory.executor import hosts
from agent_memory.executor.reasoners import ToolHostReasoner

FAKE_HOST = """#!{python}
import json, os, subprocess, sys, tomllib

argv = sys.argv[1:]
settings = None

def after(flag):
    return argv[argv.index(flag) + 1]

if "--version" in argv:
    print("Muse Code 1.4.4")
    raise SystemExit(0)

count_path = os.environ.get("FAKE_HOST_COUNT")
if count_path:
    try:
        count = int(open(count_path, encoding="utf-8").read())
    except (FileNotFoundError, ValueError):
        count = 0
    open(count_path, "w", encoding="utf-8").write(str(count + 1))

if "--query-file" in argv:
    prompt = open(after("--query-file"), encoding="utf-8").read()
    settings_path = os.path.join(os.environ["HERMES_HOME"], "config.yaml")
    settings = json.load(open(settings_path, encoding="utf-8"))
    server = next(iter(settings["mcp_servers"].values()))
    system = prompt
elif "--prompt-file" in argv:
    prompt = open(after("--prompt-file"), encoding="utf-8").read()
    settings_path = os.path.join(os.environ["XDG_CONFIG_HOME"], "muse", "settings.json")
    settings = json.load(open(settings_path, encoding="utf-8"))
    server = next(iter(settings["mcp_servers"].values()))
    system = prompt
elif "--mcp-config" in argv:
    prompt = sys.stdin.read()
    server = next(iter(json.loads(after("--mcp-config"))["mcpServers"].values()))
    system = open(after("--system-prompt-file"), encoding="utf-8").read()
else:
    prompt = sys.stdin.read()
    overrides = tomllib.loads(
        "\\n".join(argv[i + 1] for i, part in enumerate(argv) if part == "-c")
    )
    server = next(iter(overrides["mcp_servers"].values()))
    system = open(overrides["model_instructions_file"], encoding="utf-8").read()

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
replies = []
for index, (name, arguments) in enumerate(json.loads(os.environ["FAKE_HOST_SCRIPT"])):
    replies.append(rpc(index + 2, "tools/call", {{"name": name, "arguments": arguments}}))
child.stdin.close()
child.wait()

with open(os.environ["FAKE_HOST_LOG"], "w", encoding="utf-8") as log:
    json.dump({{"argv": argv, "stdin": prompt, "system": system, "listed": listed,
               "replies": replies, "executor": os.environ.get("AGENT_MEMORY_EXECUTOR"),
               "settings": settings}}, log)
if "--output-last-message" in argv:
    open(after("--output-last-message"), "w", encoding="utf-8").write("done")
if "--json" in argv:
    print(json.dumps({{"kind": "run_terminal", "terminal": "completed", "text": "done"}}))
else:
    print("done")
"""


def _fake_host(install, tmp_path, name):
    return install(tmp_path / "bin" / name, FAKE_HOST.format(python=sys.executable))


def _reasoner(name, binary):
    spec = hosts.HostSpec(name=name, binary=str(binary), model="a-model", attempts=1)
    return ToolHostReasoner(host=hosts.Host(spec))


def _batch(store):
    old = store.record(
        type="fact",
        fields={"project": "pipeline", "subject": "queue timeout"},
        abstract="Queue timeout is 20 seconds",
        body="Set in infra/queue.yaml.",
    )
    lines = ["user: Our queue timeout is 30 seconds now, raised from 20.", "assistant: Noted."]
    pointer = store.archive.append_session("boundary", lines)
    return old, sessions.resolve(store.layout, pointer)


def _supersede(handle):
    return {
        "type": "fact",
        "op": "supersede",
        "handle": handle,
        "fields": {"project": "pipeline", "subject": "queue timeout 30s"},
        "abstract": "Queue timeout is 30 seconds",
        "provenance": ["0"],
    }


@pytest.mark.parametrize(
    "name",
    [hosts.HOST_CLAUDE_CODE, hosts.HOST_CODEX, hosts.HOST_HERMES, hosts.HOST_MUSE_CODE],
)
def test_a_host_distills_a_batch_through_the_toolkit_adapter(
    name, store, tmp_path, monkeypatch, python_executable
):
    if name == hosts.HOST_HERMES:
        monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-root"))
    old, messages = _batch(store)
    log = tmp_path / "host-log.json"
    script = [
        [toolkit.TOOL_RECALL, {toolkit.ARG_QUERY: "queue timeout"}],
        [toolkit.TOOL_READ, {toolkit.ARG_NAME: old.name}],
        [toolkit.TOOL_SUBMIT, {toolkit.ARG_OPERATIONS: [_supersede(old.name)]}],
    ]
    monkeypatch.setenv("FAKE_HOST_SCRIPT", json.dumps(script))
    monkeypatch.setenv("FAKE_HOST_LOG", str(log))
    count = tmp_path / "host-count.txt"
    monkeypatch.setenv("FAKE_HOST_COUNT", str(count))

    report = distill.distill(
        store, "boundary", messages, _reasoner(name, _fake_host(python_executable, tmp_path, name))
    )

    assert report.batches[0].written == ("queue-timeout-30s",)
    assert report.batches[0].rounds == len(script)
    assert not store.find(old.name).is_active()
    seen = json.loads(log.read_text(encoding="utf-8"))
    assert set(seen["listed"]) == {toolkit.TOOL_RECALL, toolkit.TOOL_READ, toolkit.TOOL_SUBMIT}
    assert all(reply["result"]["isError"] is False for reply in seen["replies"])
    assert "our queue timeout is 30 seconds" in seen["stdin"].lower()
    assert ("our queue timeout is 30 seconds" in seen["system"].lower()) == (
        name in (hosts.HOST_HERMES, hosts.HOST_MUSE_CODE)
    )
    assert toolkit.TOOL_SUBMIT in seen["system"]
    assert seen["executor"] == "1"
    assert count.read_text(encoding="utf-8") == "1"
    if name == hosts.HOST_MUSE_CODE:
        assert "run.toolset" not in seen["settings"]
        override = seen["argv"][seen["argv"].index("-c") + 1]
        assert json.loads(override.removeprefix("run.toolset=")) == [
            "mcp__memory__recall",
            "mcp__memory__read",
            "mcp__memory__submit_operations",
        ]
        assert set(seen["settings"]["mcp_servers"]) == {"memory"}
    if name == hosts.HOST_HERMES:
        assert set(seen["settings"]["mcp_servers"]) == {hosts.HERMES_WRITE_SERVER_NAME}
        configured = seen["settings"]["mcp_servers"][hosts.HERMES_WRITE_SERVER_NAME]
        assert configured["tools"] == {
            "include": ["recall", "read", "submit_operations"],
            "resources": False,
            "prompts": False,
        }


@pytest.mark.parametrize(
    "name", [hosts.HOST_CODEX, hosts.HOST_HERMES, hosts.HOST_MUSE_CODE]
)
def test_a_host_run_without_a_submission_writes_nothing(
    name, store, tmp_path, monkeypatch, python_executable
):
    if name == hosts.HOST_HERMES:
        monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-root"))
    old, messages = _batch(store)
    monkeypatch.setenv(
        "FAKE_HOST_SCRIPT", json.dumps([[toolkit.TOOL_RECALL, {toolkit.ARG_QUERY: "queue"}]])
    )
    monkeypatch.setenv("FAKE_HOST_LOG", str(tmp_path / "host-log.json"))
    reasoner = _reasoner(name, _fake_host(python_executable, tmp_path, name))
    before = sorted(pathlib.Path(store.root).rglob("*.md"))
    with pytest.raises(ValidationError):
        distill.distill(store, "boundary", messages, reasoner)
    assert sorted(pathlib.Path(store.root).rglob("*.md")) == before
    assert store.find(old.name).is_active()
    assert Watermark(store.layout, store.clock).read("boundary").distilled == 0


def test_muse_auto_native_write_creates_a_new_memory_with_source_provenance(
    store, tmp_path, monkeypatch, python_executable
):
    pointer = store.archive.append_session(
        "muse-new", ["user: The deploy window is Friday.", "assistant: Noted."]
    )
    messages = sessions.resolve(store.layout, pointer)
    operation = {
        "type": "fact",
        "op": "new",
        "fields": {"project": "default", "subject": "deploy window"},
        "abstract": "The deploy window is Friday",
        "body": "Deployments run on Friday.",
        "provenance": ["0"],
    }
    log = tmp_path / "muse-new-log.json"
    monkeypatch.setenv(
        "FAKE_HOST_SCRIPT",
        json.dumps([[toolkit.TOOL_SUBMIT, {toolkit.ARG_OPERATIONS: [operation]}]]),
    )
    monkeypatch.setenv("FAKE_HOST_LOG", str(log))
    binary = _fake_host(python_executable, tmp_path, hosts.BINARIES[hosts.HOST_MUSE_CODE][0])
    monkeypatch.setenv("PATH", str(binary.parent) + os.pathsep + os.environ["PATH"])
    reasoner = executor_distiller.distiller(ExecutorConfig(host=hosts.HOST_MUSE_CODE))
    assert isinstance(reasoner, ToolHostReasoner)

    report = distill.distill(
        store,
        "muse-new",
        messages,
        reasoner,
    )

    assert report.batches[0].written == ("deploy-window",)
    written = store.find("deploy-window")
    assert written is not None
    assert written.provenance == ["sessions/muse-new#0-0"]


def test_muse_native_write_returns_tool_errors_to_the_same_run_then_skips(
    store, tmp_path, monkeypatch, python_executable
):
    pointer = store.archive.append_session("muse-skip", ["user: Thanks."])
    messages = sessions.resolve(store.layout, pointer)
    log = tmp_path / "muse-skip-log.json"
    script = [
        [toolkit.TOOL_READ, {toolkit.ARG_NAME: "missing-memory"}],
        [toolkit.TOOL_SUBMIT, {toolkit.ARG_OPERATIONS: [{"type": "fact", "op": "new"}]}],
        [
            toolkit.TOOL_SUBMIT,
            {toolkit.ARG_OPERATIONS: [{"type": "fact", "op": "skip"}]},
        ],
    ]
    monkeypatch.setenv("FAKE_HOST_SCRIPT", json.dumps(script))
    monkeypatch.setenv("FAKE_HOST_LOG", str(log))
    before = sorted(pathlib.Path(store.root).rglob("*.md"))

    report = distill.distill(
        store,
        "muse-skip",
        messages,
        _reasoner(
            hosts.HOST_MUSE_CODE,
            _fake_host(python_executable, tmp_path, hosts.HOST_MUSE_CODE),
        ),
    )

    assert report.batches[0].written == ()
    assert report.batches[0].rounds == len(script)
    assert sorted(pathlib.Path(store.root).rglob("*.md")) == before
    assert Watermark(store.layout, store.clock).read("muse-skip").distilled == 1
    seen = json.loads(log.read_text(encoding="utf-8"))
    assert seen["replies"][0]["result"]["isError"] is True
    assert seen["replies"][1]["result"]["isError"] is True
    assert seen["replies"][2]["result"]["isError"] is False
