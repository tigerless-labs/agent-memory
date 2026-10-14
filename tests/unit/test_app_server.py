"""Codex app-server transport stays one-process, isolated, and fail-closed."""

import json
import pathlib
import queue

import pytest
from agent_memory.core.errors import ReasonerUnavailableError
from agent_memory.executor import app_server
from agent_memory.executor.hosts import HOST_CODEX, Host, HostSpec

THREAD_ID = "018f0000-0000-7000-8000-00000000c350"


class FakeStdin:
    def __init__(self):
        self.lines = []
        self.closed = False

    def write(self, line):
        self.lines.append(json.loads(line))

    def flush(self):
        pass

    def close(self):
        self.closed = True


class FakeProcess:
    def __init__(self, events):
        self.stdin = FakeStdin()
        self.stdout = iter(json.dumps(event) + "\n" for event in events)
        self.stderr = FakeStderr()
        self.returncode = None
        self.pid = 1234
        self.terminated = False
        self.killed = False

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.returncode = 0
        return 0

    def terminate(self):
        self.terminated = True
        self.returncode = -15

    def kill(self):
        self.killed = True
        self.returncode = -9


class FakeStderr:
    @staticmethod
    def readlines():
        return []


def _events(*turn_events, ephemeral=True):
    return [
        {"id": 1, "result": {"userAgent": "test"}},
        {
            "id": 2,
            "result": {"thread": {"id": THREAD_ID, "ephemeral": ephemeral}},
        },
        *turn_events,
    ]


def _turn_events(item_type="agentMessage", status="completed"):
    return [
        {"id": 3, "result": {"turn": {"status": "inProgress"}}},
        {
            "method": "item/completed",
            "params": {"item": {"type": item_type, "text": "answer"}},
        },
        {
            "method": "thread/tokenUsage/updated",
            "params": {
                "tokenUsage": {
                    "last": {
                        "inputTokens": 21,
                        "cachedInputTokens": 13,
                        "outputTokens": 5,
                    }
                }
            },
        },
        {
            "method": "turn/completed",
            "params": {"turn": {"status": status}},
        },
    ]


def _host(timeout=1):
    return Host(
        HostSpec(
            name=HOST_CODEX,
            binary="codex",
            model="a-model",
            timeout_seconds=timeout,
        )
    )


def test_app_server_reuses_one_process_and_reports_per_turn_usage(monkeypatch, tmp_path):
    process = FakeProcess(_events(*_turn_events()))
    monkeypatch.setattr(app_server.subprocess, "Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr(
        Host,
        "isolated_codex_environment",
        lambda self, extra, scratch: {**extra, "CODEX_HOME": str(tmp_path)},
    )

    session = app_server.CodexAppServerSession(_host())
    result = session.step("question")

    assert result.ok
    assert result.text == "answer"
    assert result.session_id == THREAD_ID
    assert result.input_tokens == 21
    assert result.cached_input_tokens == 13
    assert result.output_tokens == 5
    assert session.process_starts == 1
    assert [message["method"] for message in process.stdin.lines] == [
        "initialize",
        "initialized",
        "thread/start",
        "turn/start",
    ]
    thread = process.stdin.lines[2]["params"]
    assert thread["ephemeral"] is True
    assert thread["approvalPolicy"] == "never"
    assert thread["sandbox"] == "read-only"
    turn = process.stdin.lines[3]["params"]
    assert turn["sandboxPolicy"] == {"type": "readOnly", "networkAccess": False}

    session.close()
    assert process.stdin.closed


def test_app_server_disables_host_features_and_uses_an_isolated_workdir(monkeypatch, tmp_path):
    captured = {}
    process = FakeProcess(_events())
    monkeypatch.setenv("AGENT_MEMORY_STORE", "/private/store")
    monkeypatch.setenv("AGENT_MEMORY_OBSERVATION_DIR", "/private/observations")

    def popen(command, **kwargs):
        captured["command"] = command
        captured["cwd"] = kwargs["cwd"]
        captured["env"] = kwargs["env"]
        return process

    monkeypatch.setattr(app_server.subprocess, "Popen", popen)
    monkeypatch.setattr(
        Host,
        "isolated_codex_environment",
        lambda self, extra, scratch: {**extra, "CODEX_HOME": str(tmp_path)},
    )

    session = app_server.CodexAppServerSession(_host())

    command = captured["command"]
    for feature in app_server.APP_SERVER_DISABLED_FEATURES:
        assert ["--disable", feature] == command[
            command.index(feature) - 1 : command.index(feature) + 1
        ]
    assert captured["cwd"] != tmp_path
    assert captured["env"]["AGENT_MEMORY_EXECUTOR"] == "1"
    assert "AGENT_MEMORY_STORE" not in captured["env"]
    assert "AGENT_MEMORY_OBSERVATION_DIR" not in captured["env"]
    assert captured["env"]["HOME"] != str(pathlib.Path.home())
    session.close()


def test_app_server_rejects_any_host_tool_item(monkeypatch, tmp_path):
    process = FakeProcess(_events(*_turn_events(item_type="commandExecution")))
    monkeypatch.setattr(app_server.subprocess, "Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr(
        Host,
        "isolated_codex_environment",
        lambda self, extra, scratch: {**extra, "CODEX_HOME": str(tmp_path)},
    )
    session = app_server.CodexAppServerSession(_host())

    result = session.step("question")

    assert not result.ok
    assert "forbidden item" in result.error
    assert len(session.results) == 1
    session.close()


def test_app_server_rejects_non_ephemeral_threads_and_releases_process(monkeypatch, tmp_path):
    process = FakeProcess(_events(ephemeral=False))
    monkeypatch.setattr(app_server.subprocess, "Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr(
        Host,
        "isolated_codex_environment",
        lambda self, extra, scratch: {**extra, "CODEX_HOME": str(tmp_path)},
    )

    with pytest.raises(ReasonerUnavailableError, match="not ephemeral"):
        app_server.CodexAppServerSession(_host())

    assert process.stdin.closed


def test_app_server_failed_turn_returns_no_partial_answer(monkeypatch, tmp_path):
    process = FakeProcess(_events(*_turn_events(status="failed")))
    monkeypatch.setattr(app_server.subprocess, "Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr(
        Host,
        "isolated_codex_environment",
        lambda self, extra, scratch: {**extra, "CODEX_HOME": str(tmp_path)},
    )
    session = app_server.CodexAppServerSession(_host())

    result = session.step("question")

    assert not result.ok
    assert result.text == ""
    assert "ended as 'failed'" in result.error
    session.close()


def test_app_server_rejects_server_side_tool_requests(monkeypatch, tmp_path):
    events = _events(
        {"id": 3, "result": {"turn": {"status": "inProgress"}}},
        {"id": 99, "method": "item/tool/call", "params": {"name": "memory_write"}},
    )
    process = FakeProcess(events)
    monkeypatch.setattr(app_server.subprocess, "Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr(
        Host,
        "isolated_codex_environment",
        lambda self, extra, scratch: {**extra, "CODEX_HOME": str(tmp_path)},
    )
    session = app_server.CodexAppServerSession(_host())

    result = session.step("question")

    assert not result.ok
    assert "unexpectedly requested 'item/tool/call'" in result.error
    assert session.process_starts == 1
    session.close()


def test_app_server_timeout_returns_no_answer_and_does_not_restart(monkeypatch, tmp_path):
    process = FakeProcess(_events())
    monkeypatch.setattr(app_server.subprocess, "Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr(
        Host,
        "isolated_codex_environment",
        lambda self, extra, scratch: {**extra, "CODEX_HOME": str(tmp_path)},
    )
    session = app_server.CodexAppServerSession(_host(timeout=0.001))
    session._events = queue.Queue()

    result = session.step("question")

    assert not result.ok
    assert result.text == ""
    assert result.error == "Codex app-server timed out"
    assert session.process_starts == 1
    session.close()


def test_app_server_completed_turn_requires_a_final_message(monkeypatch, tmp_path):
    events = _events(
        {"id": 3, "result": {"turn": {"status": "inProgress"}}},
        {"method": "turn/completed", "params": {"turn": {"status": "completed"}}},
    )
    process = FakeProcess(events)
    monkeypatch.setattr(app_server.subprocess, "Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr(
        Host,
        "isolated_codex_environment",
        lambda self, extra, scratch: {**extra, "CODEX_HOME": str(tmp_path)},
    )
    session = app_server.CodexAppServerSession(_host())

    result = session.step("question")

    assert not result.ok
    assert result.text == ""
    assert result.error == "missing or empty Codex final message"
    session.close()
