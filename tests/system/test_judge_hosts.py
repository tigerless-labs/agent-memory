"""Judge transport and provenance contracts, without CLI login or network calls."""

import dataclasses
import json
import subprocess
from pathlib import Path

import pytest
from agent_memory.executor import hosts
from agent_memory.harness import main as cli
from agent_memory.harness.judge import RUBRIC, Judge
from agent_memory.harness.metrics import RunMetadata, RunMetadataSink


class FakeHost(hosts.Host):
    def __init__(self, spec, calls):
        super().__init__(spec)
        self.calls = calls

    def run(self, prompt, **kwargs):
        self.calls.append((self.name, prompt, kwargs))
        return hosts.HostResult("yes" if prompt.startswith("Decide whether") else "42", True, 0.01)


def suite_file(tmp_path):
    suite = tmp_path / "fixture.json"
    suite.write_text(json.dumps([{
        "question_id": "q1", "question_type": "single-session-user",
        "question": "What is six times seven?", "answer": "42",
        "question_date": "2026/09/07", "haystack_session_ids": [],
        "haystack_dates": [], "haystack_sessions": [], "answer_session_ids": [],
    }]))
    return suite


@pytest.mark.parametrize("tested", ["claude-code", "codex"])
@pytest.mark.parametrize("judge", ["claude-code", "codex"])
def test_independent_roles_end_to_end(tmp_path, monkeypatch, tested, judge):
    calls, checked = [], []
    monkeypatch.setattr(cli, "Host", lambda spec: FakeHost(spec, calls))

    def available(spec):
        checked.append(spec.name)
        return spec.name in {tested, judge}

    monkeypatch.setattr(hosts.HostSpec, "available", available)
    workspace = tmp_path / "run"
    assert cli.main([
        "run", "--suite", str(suite_file(tmp_path)), "--workspace", str(workspace),
        "--arms", "W0", "--host", tested, "--model", "tested-model",
        "--judge-host", judge, "--judge-model", "judge-model", "--concurrency", "1",
    ]) == 0
    assert set(checked) == {tested, judge}
    tested_calls = [c for c in calls if not c[1].startswith("Decide whether")]
    judge_calls = [c for c in calls if c[1].startswith("Decide whether")]
    assert len(tested_calls) == 1 and tested_calls[0][0] == tested
    assert len(judge_calls) == 5 and {c[0] for c in judge_calls} == {judge}
    assert {c[1] for c in judge_calls} == {RUBRIC.format(
        question="What is six times seven?", expected="42", candidate="42",
    )}
    paths = [c[2]["workdir"] for c in judge_calls]
    assert len(set(paths)) == 5
    assert all(not p.exists() and not p.is_relative_to(workspace) for p in paths)
    assert all(c[2]["tools_enabled"] is False for c in judge_calls)
    assert all(c[2]["environment"]["AGENT_MEMORY_STORE"] == "" for c in judge_calls)
    metadata = json.loads((workspace / "run.json").read_text())
    assert (metadata["host"], metadata["judge_host"]) == (tested, judge)
    assert (metadata["model"], metadata["judge_model"]) == ("tested-model", "judge-model")
    record = json.loads((workspace / "runs.jsonl").read_text())
    assert record["status"] == "ok" and record["correct"]
    for field in ("recall_names", "raw_recall_names", "read_names", "recall_queries"):
        assert record[field] == []


def test_default_judge_is_historical_claude_independent_of_tested_host():
    args = cli._parser().parse_args([
        "run", "--suite", "s", "--workspace", "w", "--host", "codex",
    ])
    judge = cli._judge_host(args.judge_host, args.judge_model)
    assert judge.name == "claude-code"
    assert judge.spec.binary == "claude"
    assert judge.spec.model == cli.JUDGE_MODEL
    assert judge.spec.attempts == 3
    assert cli._judge_host("codex").spec.model == hosts.BINARIES["codex"][1]


@pytest.mark.parametrize("missing,role", [("codex", "tested host"), ("claude-code", "judge host")])
def test_missing_selected_role_is_explicit(tmp_path, monkeypatch, capsys, missing, role):
    monkeypatch.setattr(hosts.HostSpec, "available", lambda spec: spec.name != missing)
    assert cli.main([
        "run", "--suite", str(suite_file(tmp_path)), "--workspace", str(tmp_path / "run"),
        "--host", "codex", "--judge-host", "claude-code",
    ]) == 1
    assert f"{role} binary not found" in capsys.readouterr().err
    assert not (tmp_path / "run" / "run.json").exists()


def metadata(judge_host="claude-code"):
    return RunMetadata(
        run_id="r", system="agent-memory", host="codex", model="tested", judge_model="same",
        judge_host=judge_host, exam_mode="fixed", episode_fingerprint="e", reuse_stores=None,
        config={}, code_revision="revision",
    )


def test_resume_rejects_different_judge_host_even_with_same_model(tmp_path):
    sink = RunMetadataSink(tmp_path)
    sink.ensure(metadata())
    with pytest.raises(ValueError, match="another experiment"):
        sink.ensure(metadata("codex"), resume=True)
    sink.ensure(metadata(), resume=True)


def test_legacy_metadata_only_resumes_as_claude(tmp_path):
    old = metadata().as_dict()
    del old["judge_host"]
    (tmp_path / "run.json").write_text(json.dumps(old))
    sink = RunMetadataSink(tmp_path)
    sink.ensure(metadata(), resume=True)
    with pytest.raises(ValueError, match="another experiment"):
        sink.ensure(metadata("codex"), resume=True)


def test_regrading_updates_instrument_and_prevents_mixed_resume(tmp_path):
    sink = RunMetadataSink(tmp_path)
    sink.ensure(metadata())
    sink.regrade("codex", "other-model")
    written = json.loads((tmp_path / "run.json").read_text())
    assert written["judge_host"] == "codex" and written["judge_model"] == "other-model"
    for config in (metadata(), dataclasses.replace(metadata("codex"), judge_model="other-model")):
        with pytest.raises(ValueError, match="another experiment"):
            sink.ensure(config, resume=True)


@pytest.mark.parametrize("name", ["claude-code", "codex"])
@pytest.mark.parametrize("text,correct", [("yes", True), ("no", False), ("Yes.", True),
                                         ("unparseable", False), ("", False)])
def test_same_vote_parser_for_both_transports(name, text, correct, monkeypatch):
    host = hosts.Host(hosts.HostSpec(name=name, binary=name))
    monkeypatch.setattr(host, "run", lambda *a, **kw: hosts.HostResult(text, True, 0.1))
    verdict = Judge(host).grade("q", "reference", "candidate")
    assert verdict.correct is correct
    # Preserve historical handling of successful but non-yes responses.
    assert verdict.ok


@pytest.mark.parametrize("name", ["claude-code", "codex"])
def test_failed_votes_remain_unusable(name, monkeypatch):
    host = hosts.Host(hosts.HostSpec(name=name, binary=name))
    monkeypatch.setattr(host, "run", lambda *a, **kw: hosts.HostResult("", False, 0.1, "timeout"))
    verdict = Judge(host).grade("q", "r", "a")
    assert not verdict.ok and not verdict.correct and "timeout" in verdict.error


@pytest.mark.parametrize("output", [None, "", "yes"])
def test_codex_uses_only_final_message(tmp_path, monkeypatch, output):
    def run(command, **kwargs):
        assert command[command.index("--sandbox") + 1] == "read-only"
        assert "--ephemeral" in command
        assert kwargs["cwd"] == str(tmp_path)
        if output is not None:
            Path(command[command.index("--output-last-message") + 1]).write_text(output)
        return subprocess.CompletedProcess(command, 0, "yes from noisy transcript", "")

    monkeypatch.setattr(hosts.subprocess, "run", run)
    host = hosts.Host(hosts.HostSpec(name="codex", binary="codex", attempts=1))
    result = host.run("prompt", workdir=tmp_path)
    assert result.ok is bool(output)
    assert result.text == (output or "")


def test_claude_judge_has_no_tools(tmp_path):
    command = hosts.ClaudeCodeDialect().command(
        hosts.HostSpec(name="claude-code", binary="claude"), tools_enabled=False,
        system_prompt="", max_turns=8, store_root=None, answer_file=tmp_path / "answer",
    )
    assert command[command.index("--tools") + 1] == ""
    assert command[command.index("--system-prompt") + 1] == hosts.BARE_SYSTEM_PROMPT


@pytest.mark.parametrize("failure", ["timeout", "exit"])
def test_codex_transport_failures_are_not_scores(monkeypatch, failure):
    def run(command, **kwargs):
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        return subprocess.CompletedProcess(command, 7, "yes", "authentication failed")

    monkeypatch.setattr(hosts.subprocess, "run", run)
    host = hosts.Host(hosts.HostSpec(name="codex", binary="codex", attempts=1, timeout_seconds=1))
    result = host.run("judge prompt")
    assert not result.ok and not result.text
    assert result.error == ("timeout" if failure == "timeout" else "authentication failed")


@pytest.mark.parametrize("command", ["calibrate", "regrade"])
def test_other_judge_commands_select_codex_only(tmp_path, monkeypatch, command):
    calls = []
    monkeypatch.setattr(cli, "Host", lambda spec: FakeHost(spec, calls))
    monkeypatch.setattr(hosts.HostSpec, "available", lambda spec: spec.name == "codex")
    if command == "calibrate":
        cases = tmp_path / "cases.json"
        cases.write_text(json.dumps([
            {"case": "c", "question": "q", "expected": "42", "candidate": "42", "label": True},
        ]))
        args = ["--cases", str(cases)]
    else:
        (tmp_path / "questions.json").write_text(json.dumps({"q": "q"}))
        (tmp_path / "runs.jsonl").write_text("")
        args = ["--workspace", str(tmp_path)]
    assert cli.main([command, *args, "--judge-host", "codex"]) == 0
    assert all(call[0] == "codex" for call in calls)
