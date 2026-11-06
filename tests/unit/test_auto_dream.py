"""Event-driven Dreaming: durable progress, claims, recovery, and host affinity."""

from __future__ import annotations

import json
import pathlib

import pytest
from agent_memory.adapters import auto_dream, capture, detached, hook_entry, moments
from agent_memory.cli.main import main as cli_main
from agent_memory.core import dreaming
from agent_memory.core.config import OperationExecutorConfig
from agent_memory.core.errors import ReasonerUnavailableError
from agent_memory.core.locking import file_lock
from agent_memory.core.manage import Manage
from agent_memory.core.watermark import Watermark


def _complete(store, session: str, items: list[str] | None = None) -> None:
    material = items or [f"user: durable fact from {session}", "assistant: noted"]
    capture.capture(store, session, material, source="pause")
    mark = Watermark(store.layout, store.clock).read(session)
    Watermark(store.layout, store.clock).settle(session, mark.consumed)


def _enough(store) -> None:
    for number in range(store.config.manage.trigger_min_sessions):
        _complete(store, f"session-{number}")


def _twins(store) -> None:
    store.record(
        abstract="The queue drain expires before the worker lease",
        type="experience",
        body="Short.",
        name="drain-first",
    )
    store.record(
        abstract="The queue drain expires before the worker lease again",
        type="experience",
        body="Longer body with the repair.",
        name="drain-second",
    )


def test_first_claim_counts_distinct_completed_sessions_not_boundary_events(store):
    _complete(store, "same", ["user: one"])
    _complete(store, "same", ["user: one", "assistant: two"])
    assert dreaming.claim_due(store, moments.HOST_CODEX).claim is None

    _complete(store, "second")
    _complete(store, "third")
    first = dreaming.claim_due(store, moments.HOST_CODEX)
    duplicate = dreaming.claim_due(store, moments.HOST_CLAUDE_CODE)

    assert first.claim is not None
    assert first.claim.sessions == ("same", "second", "third")
    assert first.claim.host == moments.HOST_CODEX
    assert duplicate.claim is None
    assert duplicate.reason == "dream claim active"


def test_any_unfinished_write_delays_a_due_dream(store):
    _enough(store)
    capture.capture(store, "still-distilling", ["user: not written yet"], source="pause")

    result = dreaming.claim_due(store, moments.HOST_CODEX)

    assert result.claim is None
    assert result.reason == "write pipeline not settled"


def test_worker_success_resets_baseline_and_preserves_time_gate(store, clock):
    _enough(store)
    claim = dreaming.claim_due(store, moments.HOST_CODEX).claim
    assert claim is not None

    result = auto_dream.run_worker(store, claim.id, reasoner=None)

    assert result["dreamed"] is True
    assert pathlib.Path(str(result["path"])).name == f"auto-{claim.id}.md"
    assert dreaming.state(store)["status"] == dreaming.STATUS_SUCCEEDED
    for number in range(store.config.manage.trigger_min_sessions):
        _complete(store, f"later-{number}")
    assert dreaming.claim_due(store, moments.HOST_CODEX).claim is None
    clock.advance(hours=store.config.manage.trigger_min_hours + 1)
    assert dreaming.claim_due(store, moments.HOST_CODEX).claim is not None


def test_due_runner_uses_persisted_three_session_and_twenty_four_hour_gates(store, clock):
    _enough(store)
    first = auto_dream.run_due(
        store,
        None,
        reasoner_kind="none",
        trigger_source="cron",
    )
    assert first["status"] == "succeeded"

    _enough_later = [f"later-{number}" for number in range(3)]
    for session in _enough_later:
        _complete(store, session)
    early = auto_dream.run_due(
        store,
        None,
        reasoner_kind="none",
        trigger_source="cron",
    )
    assert early["status"] == "skipped"
    assert early["sessions_since"] == 3
    assert len(list(store.layout.dream_reports.glob("auto-*.md"))) == 1

    clock.advance(hours=store.config.manage.trigger_min_hours + 1)
    overdue = auto_dream.run_due(
        store,
        None,
        reasoner_kind="none",
        trigger_source="cron",
    )
    assert overdue["status"] == "succeeded"
    assert len(list(store.layout.dream_reports.glob("auto-*.md"))) == 2


def test_report_recovers_success_if_worker_died_before_state_write(store):
    _enough(store)
    claim = dreaming.claim_due(store, moments.HOST_CODEX).claim
    assert claim is not None
    report = Manage(store).sleep(dream_id=claim.id)
    assert pathlib.Path(report.path).is_file()

    result = dreaming.claim_due(store, moments.HOST_CODEX)

    assert result.claim is None
    recovered = dreaming.state(store)
    assert recovered["status"] == dreaming.STATUS_SUCCEEDED
    assert recovered["last_report"] == report.path


def test_failed_worker_is_observable_and_next_event_retries_same_decision(store):
    _twins(store)
    _enough(store)
    claim = dreaming.claim_due(store, moments.HOST_MUSE_CODE).claim
    assert claim is not None

    def unavailable(_prompt: str) -> str:
        raise RuntimeError("host unavailable")

    with pytest.raises(RuntimeError, match="host unavailable"):
        auto_dream.run_worker(store, claim.id, unavailable)

    failed = dreaming.state(store)
    assert failed["status"] == dreaming.STATUS_FAILED
    assert "host unavailable" in str(failed["last_error"])
    retried = dreaming.claim_due(store, moments.HOST_CODEX).claim
    assert retried is not None
    assert retried.id == claim.id
    assert retried.attempt == claim.attempt + 1
    assert retried.host == moments.HOST_CODEX


def test_expired_claim_recovers_without_pid_scanning(store, clock):
    store.config.manage.claim_lease_seconds = 1
    _enough(store)
    first = dreaming.claim_due(store, moments.HOST_CODEX).claim
    assert first is not None
    clock.advance(seconds=store.config.manage.claim_lease_seconds + 1)

    second = dreaming.claim_due(store, moments.HOST_CODEX).claim

    assert second is not None
    assert second.id == first.id
    assert second.attempt == first.attempt + 1


def test_expired_lease_does_not_replace_a_worker_holding_the_run_lock(store, clock):
    store.config.manage.claim_lease_seconds = 1
    _enough(store)
    first = dreaming.claim_due(store, moments.HOST_CODEX).claim
    assert first is not None
    clock.advance(seconds=store.config.manage.claim_lease_seconds + 1)

    with file_lock(store.layout.dream_run_lock, timeout=None):
        result = dreaming.claim_due(store, moments.HOST_CLAUDE_CODE)

    assert result.claim is None
    assert result.reason == "dream worker still running"
    assert dreaming.state(store)["host"] == moments.HOST_CODEX


def test_duplicate_worker_lock_timeout_does_not_mark_the_owner_failed(store):
    store.config.storage.lock_timeout_seconds = 0.01
    _enough(store)
    claim = dreaming.claim_due(store, moments.HOST_CODEX).claim
    assert claim is not None

    with file_lock(store.layout.dream_run_lock, timeout=None):
        result = auto_dream.run_worker(store, claim.id, reasoner=None)

    assert result["dreamed"] is False
    assert result["reason"] == "another dream worker still owns the run lock"
    assert dreaming.state(store)["status"] == dreaming.STATUS_RUNNING


def test_detached_launcher_uses_manage_host_and_executor_environment(store, monkeypatch):
    _enough(store)
    store.config.executor.manage = OperationExecutorConfig(
        reasoner="host", host=moments.HOST_MUSE_CODE, host_model="muse-test"
    )
    store.config.save(store.root)
    launched = {}

    def popen(command, **kwargs):
        launched.update(command=command, kwargs=kwargs)

    monkeypatch.setattr(auto_dream.subprocess, "Popen", popen)
    result = auto_dream.launch(store, trigger_source="hook")

    assert result.claim is not None
    assert result.claim.host == moments.HOST_MUSE_CODE
    assert result.claim.trigger_source == "hook"
    assert result.claim.reasoner == "host"
    assert launched["command"][-6:] == [
        "--reason",
        "host",
        "--reason-host",
        moments.HOST_MUSE_CODE,
        "--reason-model",
        "muse-test",
    ]
    assert detached.options().items() <= launched["kwargs"].items()
    assert launched["kwargs"]["stdin"] is auto_dream.subprocess.DEVNULL


def test_detached_launcher_does_not_fallback_from_explicit_endpoint(store, monkeypatch):
    _enough(store)
    store.config.executor.manage = OperationExecutorConfig(
        reasoner="endpoint", model="managed-model"
    )
    store.config.save(store.root)
    launched = {}
    monkeypatch.setattr(
        auto_dream.subprocess,
        "Popen",
        lambda command, **kwargs: launched.update(command=command, kwargs=kwargs),
    )

    result = auto_dream.launch(store, trigger_source="hook")

    assert result.claim is not None
    assert result.claim.host == "endpoint"
    assert result.claim.reasoner == "endpoint"
    assert "--reason-host" not in launched["command"]
    assert launched["command"][-4:] == [
        "--reason",
        "endpoint",
        "--reason-model",
        "managed-model",
    ]


def test_manual_sleep_covers_completed_sessions_for_automatic_counting(store):
    _enough(store)
    report = Manage(store).sleep()
    dreaming.record_manual_success(store, report.path)

    assert dreaming.claim_due(store, moments.HOST_CODEX).sessions_since == 0


def test_sleep_if_due_skips_without_a_report(store, capsys):
    before = list(store.layout.dream_reports.glob("*.md"))

    assert (
        cli_main(
            [
                "--store",
                str(store.root),
                "--json",
                "sleep",
                "--if-due",
                "--trigger-source",
                "cron",
                "--reason",
                "none",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "due": False,
        "reason": "trigger conditions not met",
        "reasoner": {"kind": "none"},
        "sessions_since": 0,
        "slept": False,
        "status": "skipped",
        "trigger_source": "cron",
    }
    assert list(store.layout.dream_reports.glob("*.md")) == before


def test_sleep_if_due_runs_t0_t1_and_records_the_actual_manage_reasoner(
    store, monkeypatch, capsys
):
    _twins(store)
    for name in ("exact-first", "exact-second"):
        store.record(
            abstract="Exact queue retention rule",
            type="fact",
            body="Keep queue receipts for thirty days.",
            name=name,
            fields={"project": "dedup", "subject": "exact-retention"},
            valid_from="2000-01-01",
        )
    _enough(store)
    store.config.executor.manage = OperationExecutorConfig(reasoner="host", host="codex")
    store.config.save(store.root)
    proposal = next(
        item
        for item in Manage(store).proposals()
        if set(item.targets) == {"drain-first", "drain-second"}
    )
    selected = []

    def reasoner(config):
        selected.append(config)
        return lambda _prompt: json.dumps({"proposal": proposal.id, "verdict": "reject"})

    monkeypatch.setattr("agent_memory.executor.distiller.distiller", reasoner)

    assert (
        cli_main(
            [
                "--store",
                str(store.root),
                "--json",
                "sleep",
                "--if-due",
                "--trigger-source",
                "cron",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["due"] is True
    assert payload["slept"] is True
    assert payload["status"] == "succeeded"
    assert payload["trigger_source"] == "cron"
    assert payload["reasoner"] == {"kind": "host", "host": "codex"}
    assert selected[-1].host == "codex"
    assert any(action["kind"] == "duplicate-merged" for action in payload["actions"])
    assert [decision["proposal"] for decision in payload["decisions"]] == [proposal.id]
    assert pathlib.Path(payload["path"]).is_file()
    ledger = store.layout.dream_reports / "decisions.md"
    assert proposal.id in ledger.read_text(encoding="utf-8")


def test_sleep_if_due_reasoner_failure_is_persisted_without_a_report(
    store, monkeypatch, capsys
):
    _twins(store)
    _enough(store)
    store.config.executor.manage = OperationExecutorConfig(reasoner="host", host="codex")
    store.config.save(store.root)

    def unavailable(_prompt: str) -> str:
        raise ReasonerUnavailableError("configured Codex unavailable")

    monkeypatch.setattr(
        "agent_memory.executor.distiller.distiller", lambda _config: unavailable
    )

    assert (
        cli_main(
            ["--store", str(store.root), "--json", "sleep", "--if-due"]
        )
        == 1
    )

    error = json.loads(capsys.readouterr().err)
    assert error["code"] == "reasoner_unavailable"
    status = dreaming.state(store)
    assert status["status"] == dreaming.STATUS_FAILED
    assert status["host"] == "codex"
    assert status["reasoner"] == "host"
    assert "configured Codex unavailable" in str(status["last_error"])
    assert not list(store.layout.dream_reports.glob("auto-*.md"))


def test_duplicate_boundary_is_still_a_retry_tick_without_incrementing_sessions(store):
    event = {
        "host": moments.HOST_CODEX,
        "hook_event_name": "Stop",
        "session_id": "same",
        "items": ["user: one"],
    }
    hook_entry.handle(store, event, launch=lambda *_: True, dream_launch=lambda *_: None)
    launches = []

    response = hook_entry.handle(
        store,
        event,
        launch=lambda *_: pytest.fail("duplicate boundary must not redistill"),
        dream_launch=lambda *args: launches.append(args),
    )

    assert response == {}
    assert launches == [(store, moments.HOST_CODEX)]
    assert len(dreaming.completed_sessions(store)) == 0


def test_session_start_is_the_next_event_time_threshold_tick(store):
    launches = []

    hook_entry.handle(
        store,
        {"host": moments.HOST_CODEX, "hook_event_name": "SessionStart"},
        dream_launch=lambda *args: launches.append(args),
    )

    assert launches == [(store, moments.HOST_CODEX)]


def test_dream_status_exposes_failure_and_retry_progress(store, capsys):
    _enough(store)
    claim = dreaming.claim_due(store, moments.HOST_CODEX).claim
    assert claim is not None
    dreaming.mark_failed(store, claim.id, "Codex unavailable")

    assert cli_main(["--store", str(store.root), "--json", "dream-status"]) == 0

    output = capsys.readouterr().out
    assert '"status": "failed"' in output
    assert '"sessions_since": 3' in output
    assert "Codex unavailable" in output


def test_hook_distill_checks_dream_only_after_watermark_settles(
    store, monkeypatch, capsys
):
    store.config.manage.trigger_min_sessions = 1
    store.config.save(store.root)
    capture.capture(store, "boundary", ["user: remember the blue queue"], source="pause")
    observed = []

    monkeypatch.setattr(
        "agent_memory.executor.distiller.distiller", lambda _config: lambda _prompt: "{}"
    )
    monkeypatch.setattr(
        auto_dream,
        "launch",
        lambda launched_store, *, trigger_source: observed.append(
            (Watermark(launched_store.layout).read("boundary"), trigger_source)
        )
        or dreaming.ClaimResult(None, "observed", 1),
    )

    assert (
        cli_main(
            [
                "--store",
                str(store.root),
                "--json",
                "distill",
                "--session",
                "boundary",
                "--source-host",
                moments.HOST_CODEX,
                "--auto-dream",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert len(observed) == 1
    mark, trigger_source = observed[0]
    assert mark.distilled == mark.consumed == 1
    assert trigger_source == "hook"


def test_hook_distill_uses_manage_host_instead_of_source_host(store, monkeypatch, capsys):
    store.config.manage.trigger_min_sessions = 1
    store.config.executor.manage = OperationExecutorConfig(
        reasoner="host", host=moments.HOST_MUSE_CODE
    )
    store.config.save(store.root)
    capture.capture(store, "boundary", ["user: remember the green queue"], source="pause")
    launched = {}
    monkeypatch.setattr(
        "agent_memory.executor.distiller.distiller",
        lambda _config: lambda _prompt: json.dumps(
            {
                "type": "fact",
                "fields": {"project": "queue", "subject": "colour"},
                "abstract": "The queue is green",
                "provenance": ["0"],
            }
        ),
    )
    monkeypatch.setattr(
        auto_dream.subprocess,
        "Popen",
        lambda command, **kwargs: launched.update(command=command, kwargs=kwargs),
    )

    assert (
        cli_main(
            [
                "--store",
                str(store.root),
                "--json",
                "distill",
                "--session",
                "boundary",
                "--source-host",
                moments.HOST_CODEX,
                "--auto-dream",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)

    assert payload["auto_dream"]["host"] == moments.HOST_MUSE_CODE
    assert launched["command"][-2:] == ["--reason-host", moments.HOST_MUSE_CODE]
    state = dreaming.state(store)
    assert state["host"] == moments.HOST_MUSE_CODE
    assert state["trigger_source"] == "hook"
