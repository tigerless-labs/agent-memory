"""Every trigger means the same thing: distill the archived backlog. None is required."""

import json

from agent_memory.adapters import capture as capture_module
from agent_memory.cli.main import main
from agent_memory.core import triggers
from agent_memory.core.watermark import Mark, Watermark

LINES = [
    "user: we moved the deploy to Fridays",
    "assistant: noted",
    "user: and the queue timeout is 30 seconds now",
]


def _mark(updated_at="2026-01-15T10:00:00+00:00"):
    return Mark(session="s", consumed=len(LINES), updated_at=updated_at, source="", distilled=0)


def _backlog(store, session="s", lines=LINES):
    capture_module.capture(store, session, lines)
    return triggers.backlog(store.layout, session, Watermark(store.layout, store.clock))


def test_a_boundary_is_always_due_and_an_empty_backlog_never_is(store):
    backlog = _backlog(store)
    config = store.config.write
    assert triggers.reason_for(config, _mark(), backlog, "", True) == triggers.REASON_BOUNDARY
    assert triggers.reason_for(config, _mark(), [], "", True) is None


def test_the_message_threshold_fires_without_any_hook(store):
    backlog = _backlog(store)
    config = store.config.write
    config.pending_message_threshold = len(backlog)
    assert triggers.reason_for(config, _mark(), backlog, "", False) == triggers.REASON_MESSAGES
    config.pending_message_threshold = len(backlog) + 1
    assert triggers.reason_for(config, _mark(), backlog, "", False) is None


def test_the_token_threshold_is_measured_in_characters_over_the_configured_ratio(store):
    backlog = _backlog(store)
    config = store.config.write
    chars = sum(len(message.text) for message in backlog)
    config.pending_message_threshold = len(backlog) + 1
    config.chars_per_token = 1
    config.pending_token_threshold = chars
    assert triggers.reason_for(config, _mark(), backlog, "", False) == triggers.REASON_TOKENS
    config.pending_token_threshold = chars + 1
    assert triggers.reason_for(config, _mark(), backlog, "", False) is None


def test_an_idle_session_becomes_due_after_the_configured_silence(store):
    backlog = _backlog(store)
    config = store.config.write
    config.pending_message_threshold = len(backlog) + 1
    config.idle_seconds = 60.0
    stamp = "2026-01-15T10:00:00+00:00"
    assert (
        triggers.reason_for(config, _mark(stamp), backlog, "2026-01-15T10:00:30+00:00", False)
        is None
    )
    assert (
        triggers.reason_for(config, _mark(stamp), backlog, "2026-01-15T10:01:00+00:00", False)
        == triggers.REASON_IDLE
    )


def _stub_executor(monkeypatch, reply):
    monkeypatch.setattr(
        "agent_memory.executor.distiller.distiller", lambda config: lambda prompt: reply
    )


def _spec(subject, abstract, provenance):
    return json.dumps(
        {
            "type": "fact",
            "fields": {"project": "deploy", "subject": subject},
            "abstract": abstract,
            "provenance": [provenance],
        }
    )


def test_the_distill_command_runs_the_executor_over_a_named_session(store, monkeypatch, capsys):
    capture_module.capture(store, "hooked", LINES)
    _stub_executor(monkeypatch, _spec("deploy day", "Deploys happen on Fridays", "0"))
    code = main(["--store", str(store.root), "--json", "distill", "--session", "hooked"])
    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["distilled"][0]["reason"] == triggers.REASON_BOUNDARY
    assert report["distilled"][0]["batches"][0]["written"] == ["deploy-day"]
    assert Watermark(store.layout).read("hooked").distilled == len(LINES)


def test_the_scan_distills_only_sessions_past_a_threshold_and_records_why(
    store, monkeypatch, capsys
):
    capture_module.capture(store, "long", LINES)
    capture_module.capture(store, "short", LINES[:1])
    store.config.write.pending_message_threshold = len(LINES)
    store.config.write.idle_seconds = 10**9
    store.config.save(store.root)
    _stub_executor(monkeypatch, _spec("deploy day", "Deploys happen on Fridays", "0"))
    main(["--store", str(store.root), "--json", "distill"])
    report = json.loads(capsys.readouterr().out)
    assert [(item["session"], item["reason"]) for item in report["distilled"]] == [
        ("long", triggers.REASON_MESSAGES)
    ]
    assert Watermark(store.layout).read("short").distilled == 0


def test_the_threshold_path_and_the_boundary_path_write_the_same_memories(
    store, monkeypatch, capsys
):
    reply = _spec("queue timeout", "Queue timeout is 30 seconds", "2")
    _stub_executor(monkeypatch, reply)
    capture_module.capture(store, "by-hook", LINES)
    main(["--store", str(store.root), "--json", "distill", "--session", "by-hook"])
    capsys.readouterr()
    by_hook = {record.name: record.provenance for record in store.records()}

    capture_module.capture(store, "by-scan", LINES)
    store.config.write.pending_message_threshold = len(LINES)
    store.config.save(store.root)
    main(["--store", str(store.root), "--json", "distill"])
    capsys.readouterr()
    by_scan = {record.name: record.provenance for record in store.records()}
    assert set(by_hook) == {"queue-timeout"}
    assert set(by_scan) == set(by_hook)
