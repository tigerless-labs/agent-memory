"""Muse is one more host dialect; these tests require no Muse installation or user config."""

import json
import pathlib
import subprocess

import pytest
from agent_memory.adapters import hook_entry, moments, setup, transcript
from agent_memory.core import injection, sessions
from agent_memory.core.errors import ValidationError
from agent_memory.executor import hosts
from agent_memory.harness import main as harness
from agent_memory.mcp import server as mcp_server


def test_muse_host_id_and_alias_are_canonical():
    assert setup.canonical_host("muse-code") == moments.HOST_MUSE_CODE
    assert setup.canonical_host("muse") == moments.HOST_MUSE_CODE
    with pytest.raises(ValidationError, match="unsupported host"):
        setup.canonical_host("not-a-host")


def test_muse_probe_checks_path_and_version(monkeypatch):
    calls = []
    monkeypatch.setattr(setup.shutil, "which", lambda binary: "/opt/bin/muse")

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, "Muse Code 1.3.0\n", "")

    monkeypatch.setattr(setup.subprocess, "run", run)
    assert setup.probe("muse-code") == "Muse Code 1.3.0"
    assert calls[0][0] == ["/opt/bin/muse", "--version"]

    monkeypatch.setattr(setup.shutil, "which", lambda binary: None)
    with pytest.raises(ValidationError, match="install it and retry"):
        setup.probe("muse-code")


def test_muse_settings_path_honours_xdg_and_home(tmp_path):
    xdg = tmp_path / "xdg"
    assert setup.default_settings_path(
        "muse-code", {"XDG_CONFIG_HOME": str(xdg), "HOME": "/ignored"}
    ) == xdg / "muse" / "settings.json"
    assert setup.default_settings_path(
        "muse-code", {"HOME": str(tmp_path / "home")}
    ) == tmp_path / "home" / ".config" / "muse" / "settings.json"


def test_muse_setup_preserves_settings_hooks_and_mcp_and_is_idempotent(tmp_path, monkeypatch):
    target = tmp_path / "settings.json"
    original = {
        "schema_version": 1,
        "theme": "dark",
        "mcp_servers": {"other": {"transport": "stdio", "command": "other-server"}},
        "hooks": {
            "Stop": [
                {"hooks": [{"type": "command", "command": "existing-hook"}]}
            ],
            "UserPromptSubmit": [
                {"hooks": [{"type": "command", "command": "prompt-hook"}]}
            ],
        },
    }
    target.write_text(json.dumps(original), encoding="utf-8")
    replacements = []
    original_replace = pathlib.Path.replace

    def replace(path, destination):
        replacements.append((path, destination))
        return original_replace(path, destination)

    monkeypatch.setattr(pathlib.Path, "replace", replace)

    setup.install("muse-code", target)
    once = json.loads(target.read_text(encoding="utf-8"))
    setup.install("muse-code", target)
    twice = json.loads(target.read_text(encoding="utf-8"))

    assert once == twice
    assert len(replacements) == 1
    assert all(destination == target for _, destination in replacements)
    assert twice["theme"] == "dark"
    assert twice["mcp_servers"] == original["mcp_servers"]
    assert twice["hooks"]["UserPromptSubmit"] == original["hooks"]["UserPromptSubmit"]
    assert twice["hooks"]["Stop"][0] == original["hooks"]["Stop"][0]
    for event in moments.DIALECTS[moments.HOST_MUSE_CODE]:
        rendered = json.dumps(twice["hooks"][event])
        assert rendered.count("mem-hook --host muse-code") == 1


def test_new_muse_settings_get_required_schema_version(tmp_path):
    target = tmp_path / "muse" / "settings.json"
    setup.install("muse-code", target)
    assert json.loads(target.read_text(encoding="utf-8"))["schema_version"] == 1


def test_malformed_muse_settings_fail_without_overwrite(tmp_path):
    target = tmp_path / "settings.json"
    malformed = b'{"schema_version": 1, nope'
    target.write_bytes(malformed)
    with pytest.raises(ValidationError, match="malformed JSON"):
        setup.install("muse-code", target)
    assert target.read_bytes() == malformed


@pytest.mark.parametrize(
    ("event", "moment"),
    [
        ("SessionStart", moments.MOMENT_INJECT),
        ("PreCompact", moments.MOMENT_EVICT),
        ("Stop", moments.MOMENT_PAUSE),
        ("SessionEnd", moments.MOMENT_PAUSE),
    ],
)
def test_muse_hook_events_normalize_to_existing_moments(event, moment):
    raw = {
        "hook_event_name": event,
        "session_id": "muse-session",
        "cwd": "/workspace",
        "transcript_path": None,
    }
    normalized = hook_entry.normalize_event(raw, "muse-code")
    assert normalized["host"] == "muse-code"
    assert moments.moment_for(str(normalized["host"]), event) == moment
    assert normalized["session_id"] == raw["session_id"]


def test_muse_session_start_uses_muse_json_context_schema(seeded):
    response = hook_entry.handle(
        seeded,
        {"host": "muse-code", "hook_event_name": "SessionStart", "source": "startup"},
    )
    specific = response["hookSpecificOutput"]
    assert specific == {
        "hookEventName": "SessionStart",
        "additionalContext": injection.payload(seeded),
    }


def test_muse_root_session_is_normalized_and_child_log_is_ignored(tmp_path):
    fixture = pathlib.Path(__file__).parents[1] / "fixtures" / "muse" / "session.jsonl"
    assert transcript.items(fixture, host="muse-code") == [
        "user: Remember that the deploy window is Friday.",
        "assistant: I will remember the Friday deploy window.",
    ]
    child = tmp_path / "subagent" / "child" / "session.jsonl"
    child.parent.mkdir(parents=True)
    child.write_bytes(fixture.read_bytes())
    assert transcript.items(child, host="muse-code") == []


@pytest.mark.parametrize("event", ["PreCompact", "Stop", "SessionEnd"])
def test_muse_boundaries_use_existing_capture_path(store, event):
    launches = []
    response = hook_entry.handle(
        store,
        {
            "host": "muse-code",
            "hook_event_name": event,
            "session_id": "muse-root",
            "items": ["user: remember blue", "assistant: noted"],
        },
        launch=lambda root, session: launches.append((root.root, session)) or True,
    )
    assert response["moment"] == moments.moment_for("muse-code", event)
    assert launches == [(store.root, "muse-root")]
    assert len(sessions.read(store.layout, "muse-root")) == 2


def test_muse_executor_uses_prompt_file_default_model_and_sandbox(tmp_path):
    dialect = hosts.DIALECTS[hosts.HOST_MUSE_CODE]
    spec = hosts.HostSpec(name="muse-code", binary="muse", model="")
    command = dialect.command(
        spec,
        tools_enabled=True,
        system_prompt="keeper",
        max_turns=7,
        store_root=tmp_path / "run" / "store",
        answer_file=tmp_path / "prompt" / "answer.txt",
        workdir=tmp_path / "run" / "cwd",
    )
    assert command[:3] == ["muse", "exec", "--json"]
    assert "--prompt-file" in command and "--max-model-steps" in command
    assert "--model" not in command
    assert "--yolo" not in command and "--disable-sandbox" not in command
    assert command[command.index("--workspace") + 1] == str(tmp_path / "run")


def test_muse_executor_passes_explicit_model_and_effort(tmp_path):
    spec = hosts.HostSpec(
        name="muse-code", binary="muse", model="explicit-model", reasoning_effort="high"
    )
    command = hosts.DIALECTS[hosts.HOST_MUSE_CODE].command(
        spec,
        tools_enabled=False,
        system_prompt="",
        max_turns=1,
        store_root=None,
        answer_file=tmp_path / "answer.txt",
        workdir=tmp_path,
    )
    assert command[command.index("--model") + 1] == "explicit-model"
    assert command[command.index("--reasoning-effort") + 1] == "high"


def test_muse_executor_refuses_workspace_with_native_memory(tmp_path):
    native = tmp_path / ".agents" / "memory"
    native.mkdir(parents=True)
    with pytest.raises(ValueError, match="native .agents/memory"):
        hosts.DIALECTS[hosts.HOST_MUSE_CODE].command(
            hosts.HostSpec(name="muse-code", binary="muse", model=""),
            tools_enabled=False,
            system_prompt="",
            max_turns=1,
            store_root=None,
            answer_file=tmp_path / "answer.txt",
            workdir=tmp_path,
        )


def test_muse_executor_materializes_prompt_and_reads_final_jsonl(tmp_path, monkeypatch):
    observed = {}

    def run(command, **kwargs):
        prompt_path = pathlib.Path(command[command.index("--prompt-file") + 1])
        observed["prompt"] = prompt_path.read_text(encoding="utf-8")
        observed["stdin"] = kwargs["input"]
        stdout = '\n'.join(
            [
                json.dumps({"kind": "progress", "text": "not final"}),
                json.dumps({"kind": "run_terminal", "terminal": "completed", "text": "final"}),
            ]
        )
        return subprocess.CompletedProcess(command, 0, stdout, "")

    monkeypatch.setattr(hosts.subprocess, "run", run)
    host = hosts.Host(
        hosts.HostSpec(name="muse-code", binary="muse", model="", attempts=1)
    )
    result = host.run("question", system_prompt="system", workdir=tmp_path)
    assert result.ok and result.text == "final"
    assert observed == {"prompt": "system\n\nquestion", "stdin": ""}


def test_muse_executor_reads_enveloped_final_answer(tmp_path):
    stdout = json.dumps(
        {
            "payload_type": "session.event",
            "payload": {"event": {"kind": "final_answer", "text": "nested final"}},
        }
    )
    assert hosts.DIALECTS[hosts.HOST_MUSE_CODE].answer(
        stdout, tmp_path / "unused"
    ) == "nested final"


def test_mcp_memory_tool_calls_use_host_neutral_observation(store, tmp_path, monkeypatch):
    evidence = tmp_path / "observation"
    monkeypatch.setenv("AGENT_MEMORY_OBSERVATION_DIR", str(evidence))
    response = mcp_server.handle(
        store,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "memory_recall", "arguments": {"query": "muse"}},
        },
    )
    assert response is not None and "result" in response
    events = [json.loads(line) for line in (evidence / "tools.jsonl").read_text().splitlines()]
    mcp_events = [event for event in events if event["kind"].startswith("mcp_tool_")]
    assert [(event["kind"], event["tool"]) for event in mcp_events] == [
        ("mcp_tool_call", "memory_recall"),
        ("mcp_tool_return", "memory_recall"),
    ]


def test_experiment_parser_selects_muse_host_and_independent_judge():
    args = harness._parser().parse_args(
        [
            "run",
            "--suite",
            "suite.json",
            "--workspace",
            "run",
            "--host",
            "muse-code",
            "--judge-host",
            "codex",
        ]
    )
    assert (args.host, args.judge_host) == ("muse-code", "codex")
    reverse = harness._parser().parse_args(
        [
            "run",
            "--suite",
            "suite.json",
            "--workspace",
            "run",
            "--host",
            "codex",
            "--judge-host",
            "muse-code",
        ]
    )
    assert (reverse.host, reverse.judge_host) == ("codex", "muse-code")
    muse_judge = harness._judge_host("muse-code", "judge-model", reasoning_effort="xhigh")
    assert muse_judge.spec.binary == "muse"
    assert muse_judge.spec.model == "judge-model"
    assert muse_judge.spec.reasoning_effort == "xhigh"


def test_interop_parser_accepts_three_ordered_muse_smoke_pairs():
    args = harness._parser().parse_args(
        [
            "interop",
            "--workspace",
            "run",
            "--pairs",
            "muse-code:muse-code,muse-code:codex,codex:muse-code",
        ]
    )
    assert args.pairs.split(",") == [
        "muse-code:muse-code",
        "muse-code:codex",
        "codex:muse-code",
    ]
