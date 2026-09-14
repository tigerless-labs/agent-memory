"""Passive exam evidence contracts. Fake decisions are not model evidence."""

import dataclasses
import json
import os
import subprocess
import sys
from pathlib import Path

from agent_memory.core import observation
from agent_memory.core.store import Store
from agent_memory.executor.hosts import Host, HostResult, HostSpec
from agent_memory.harness.arms import BY_NAME
from agent_memory.harness.dataset import Episode
from agent_memory.harness.driver import Driver
from agent_memory.harness.judge import Verdict


class FakeHost(Host):
    def __init__(self, script):
        super().__init__(HostSpec(name="codex", binary="unused", attempts=1))
        self.script = script
        self.outputs = []

    def run(self, prompt, store_root=None, environment=None, **kwargs):
        env = {**os.environ, **environment}

        def call(*args):
            command = [
                sys.executable,
                "-c",
                "from agent_memory.cli.main import main; raise SystemExit(main())",
                "--store",
                str(store_root),
                "--json",
                *args,
            ]
            completed = subprocess.run(command, env=env, capture_output=True, text=True)
            assert completed.returncode == 0, completed.stderr
            # Repeat on a separate clone would alter usage timestamps. Instead compare
            # exact emitted CLI JSON with the observed return below.
            output = json.loads(completed.stdout)
            self.outputs.append(output)
            return output

        answer = self.script(call)
        return HostResult(answer, True, 0.01)


class FakeJudge:
    def grade(self, question, expected, candidate):
        return Verdict(correct=candidate == expected, ok=True, seconds=0, raw="fake")


def execute(tmp_path, script, expected, setup):
    root = tmp_path / "reused" / "W2" / "fixture"
    store = Store(root)
    store.init()
    setup(store)
    before = {str(p): p.read_bytes() for p in store.layout.truth_files()}
    host = FakeHost(script)
    episode = Episode(
        id="fixture",
        question_type="fixture",
        question="Synthetic question?",
        answer=expected,
        sessions=(),
        question_date="2026-01-15",
        evidence_session_ids=(),
    )
    driver = Driver(
        host,
        FakeJudge(),
        tmp_path / "stage" / "stores",
        1,
        "fixture",
        "fixed",
        reuse_stores=tmp_path / "reused",
        observe_reads=True,
    )
    result = driver.run(episode, BY_NAME["W2"])
    assert result.correct
    assert before == {str(p): p.read_bytes() for p in store.layout.truth_files()}
    events = [
        json.loads(line)
        for line in (Path(result.observation_path) / "tools.jsonl").read_text().splitlines()
    ]
    starts = [e for e in events if e["kind"] == "tool_start"]
    returns = [e for e in events if e["kind"] == "tool_return"]
    assert [e["call_id"] for e in starts] == [e["call_id"] for e in returns]
    assert [e["result"] for e in returns] == host.outputs
    assert result.observation_revision == observation.REVISION
    assert "Synthetic question" not in json.dumps(dataclasses.asdict(result))
    return events


def test_zero_hit_deep_and_read_levels(tmp_path):
    def setup(store):
        store.record(
            name="known",
            abstract="known",
            body="# Detail\nknown body",
            type="fact",
        )

    def script(call):
        assert call("recall", "zzqnonexistent", "--deep")["hits"] == []
        for level in ("abstract", "outline", "full"):
            assert call("read", "known", "--level", level)["level"] == level
        return "done"

    events = execute(tmp_path, script, "done", setup)
    recall = next(e for e in events if e["kind"] == "recall_return")
    assert recall["deep"] is True and recall["hits"] == []
    assert [e["level"] for e in events if e["kind"] == "read_return"] == [
        "abstract",
        "outline",
        "full",
    ]


def test_host_transcript_limits_and_failure(tmp_path, monkeypatch):
    from agent_memory.executor.hosts import Host

    host = Host(HostSpec(name="codex", binary="unused", attempts=2, retry_backoff_seconds=0))

    def run(*args, **kwargs):
        return subprocess.CompletedProcess(args, 1, "x" * 100000, "token=private-value")

    monkeypatch.setattr(subprocess, "run", run)
    result = host.run("DO NOT LOG PROMPT", environment={observation.ENV: str(tmp_path)})
    assert not result.ok
    text = (tmp_path / "host.jsonl").read_text()
    assert "private-value" not in text and "DO NOT LOG PROMPT" not in text
    events = [json.loads(line) for line in text.splitlines()]
    assert len({e["attempt_id"] for e in events}) == 2
    assert all(e["stdout"]["truncated"] for e in events if e["state"] == "completed")
    assert (tmp_path / "host.jsonl").stat().st_mode & 0o777 == 0o600


def test_observation_capacity_and_io_failure_are_passive(tmp_path, monkeypatch):
    monkeypatch.setattr(observation, "MAX_BYTES", 512)
    for _ in range(30):
        observation.emit("example", directory=str(tmp_path), text="a" * 100)
    lines = (tmp_path / "tools.jsonl").read_text().splitlines()
    assert json.loads(lines[-1])["kind"] == "evidence_limit"
    assert (tmp_path / "tools.jsonl").stat().st_size <= 512
    observation.emit("example", directory=str(tmp_path / "tools.jsonl"))


def test_observation_on_off_preserves_cli_bytes_and_core_returns(
    store,
    tmp_path,
    monkeypatch,
    capsys,
):
    from agent_memory.cli import main as cli

    store.record(
        name="known",
        abstract="known ticket",
        body="ticket body",
        type="fact",
    )
    store.archive.append_session("old", "known ticket history")
    store.sync_index()
    monkeypatch.setattr(cli, "Store", lambda *args, **kwargs: store)
    commands = [
        ("recall", "known ticket"),
        ("recall", "known ticket", "--deep"),
        ("context", "known ticket", "--deep"),
        ("read", "known", "--level", "full"),
        ("recall", "zzqnonexistent", "--deep"),
        ("read", "absent"),
    ]
    for command in commands:
        monkeypatch.delenv(observation.ENV, raising=False)
        before = cli.main(["--json", *command]), capsys.readouterr()
        monkeypatch.setenv(observation.ENV, str(tmp_path / "evidence"))
        after = cli.main(["--json", *command]), capsys.readouterr()
        assert before == after
    events = [
        json.loads(line)
        for line in (tmp_path / "evidence" / "tools.jsonl").read_text().splitlines()
    ]
    assert any(e["kind"] == "tool_error" for e in events)


def test_host_timeout_preserves_partial_transcript(tmp_path, monkeypatch):
    def run(*args, **kwargs):
        raise subprocess.TimeoutExpired("fake", 1, output=b"partial tool call", stderr=b"partial")

    monkeypatch.setattr(subprocess, "run", run)
    host = Host(HostSpec(name="codex", binary="unused", attempts=1))
    result = host.run("prompt", environment={observation.ENV: str(tmp_path)})
    assert result.error == "timeout"
    events = [json.loads(line) for line in (tmp_path / "host.jsonl").read_text().splitlines()]
    assert events[-1]["state"] == "timeout"
    assert events[-1]["stdout"] == "partial tool call"
