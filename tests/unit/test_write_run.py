"""The Write job runner: the fence, the trace, the heartbeat, and the drain."""

from __future__ import annotations

import json
import pathlib

import pytest
from agent_memory.adapters import capture
from agent_memory.core import distill as distill_module
from agent_memory.core import store as store_module
from agent_memory.core import triggers, write_jobs, write_run
from agent_memory.core.errors import ReasonerUnavailableError
from agent_memory.core.watermark import Watermark
from agent_memory.core.write_jobs import (
    STATE_FAILED,
    STATE_QUEUED,
    STATE_RUNNING,
    STATE_SUCCEEDED,
    WriteJobs,
)


def _capture(store, session: str = "boundary", count: int = 2) -> None:
    capture.capture(
        store,
        session,
        [f"user: the {session} queue timeout is {30 + number} seconds" for number in range(count)],
        source="pause",
    )


def _operation(subject: str = "timeout") -> dict[str, object]:
    return {
        "op": "new",
        "type": "fact",
        "fields": {"project": "queue", "subject": subject},
        "abstract": f"The queue {subject} is 30 seconds",
        "provenance": ["0"],
    }


def _ask(calls: list[str], operation: dict[str, object] | None = None):
    def ask(_prompt: str) -> str:
        calls.append(_prompt)
        return json.dumps(operation or _operation())

    return ask


def _staged_asks(*subjects: str):
    operations = [_operation(subject) for subject in subjects]

    def ask(_prompt: str) -> str:
        return json.dumps(operations.pop(0))

    return ask


def _events(path: pathlib.Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_a_job_distills_its_backlog_and_completes(store):
    _capture(store)
    job = WriteJobs(store).enqueue("boundary", "codex")
    calls: list[str] = []

    payload = write_run.run_job(store, job.id, _ask(calls), owner="worker-1")

    assert payload["status"] == "succeeded"
    assert payload["reason"] == "distilled"
    assert payload["distilled"][0]["batches"][0]["written"]
    assert Watermark(store.layout, store.clock).read("boundary").distilled == 2
    assert WriteJobs(store).get(job.id).state == STATE_SUCCEEDED
    events = _events(pathlib.Path(job.trace))
    assert events[0]["event"] == "run_started"
    assert events[0]["job"] == job.id
    assert events[0]["target"] == 2
    assert events[-1]["event"] == "run_finished"
    assert events[-1]["written"] == 1


def test_the_fence_completes_a_settled_job_without_a_reasoner_call(store):
    _capture(store)
    job = WriteJobs(store).enqueue("boundary", "codex")
    mark = Watermark(store.layout, store.clock).read("boundary")
    Watermark(store.layout, store.clock).settle("boundary", mark.consumed)

    def ask(_prompt: str) -> str:
        raise AssertionError("the fence must complete the job without reasoning")

    payload = write_run.run_job(store, job.id, ask, owner="worker-1")

    assert payload["status"] == "succeeded"
    assert payload["reason"] == "already distilled"
    assert store.records() == []
    assert WriteJobs(store).get(job.id).state == STATE_SUCCEEDED


def test_a_worker_that_dies_after_the_watermark_settles_never_repeats_the_write(store):
    _capture(store)
    job = WriteJobs(store).enqueue("boundary", "codex")
    backlog = triggers.backlog(store.layout, "boundary", Watermark(store.layout, store.clock))
    first: list[str] = []
    distill_module.distill(store, "boundary", backlog, _ask(first))
    names = [record.name for record in store.records()]
    store.clock.advance(seconds=store.config.write.jobs.lease_seconds + 1)
    later: list[str] = []

    payload = write_run.run_job(store, job.id, _ask(later), owner="worker-2")

    assert later == []
    assert payload["reason"] == "already distilled"
    assert [record.name for record in store.records()] == names
    assert WriteJobs(store).get(job.id).state == STATE_SUCCEEDED


def test_a_failing_reasoner_fails_the_job_and_schedules_a_redacted_retry(store):
    _capture(store)
    job = WriteJobs(store).enqueue("boundary", "codex")

    def ask(_prompt: str) -> str:
        raise ReasonerUnavailableError("claude unavailable; token sk-ABCDEFGHIJKLMNOPQR")

    with pytest.raises(ReasonerUnavailableError):
        write_run.run_job(store, job.id, ask, owner="worker-1")

    failed = WriteJobs(store).get(job.id)
    assert failed.state == STATE_FAILED
    assert failed.not_before
    assert "sk-" not in failed.last_error
    assert "[REDACTED]" in failed.last_error
    assert len(failed.last_error) <= store.config.write.jobs.error_max_chars
    assert "sk-" not in pathlib.Path(job.trace).read_text(encoding="utf-8")


def test_drain_runs_every_due_job_and_stands_down_when_none_is_left(store, clock):
    _capture(store, "first")
    WriteJobs(store).enqueue("first", "codex")
    clock.advance(seconds=1)
    _capture(store, "second")
    WriteJobs(store).enqueue("second", "codex")

    drained = write_run.drain(store, _staged_asks("first", "second"), owner="worker-1")

    assert [item["session"] for item in drained] == ["first", "second"]
    assert len(store.records()) == 2
    assert write_run.drain(store, _staged_asks(), owner="worker-1") == []


def test_drain_respects_its_limit_and_leaves_the_rest_queued(store, clock):
    _capture(store, "first")
    WriteJobs(store).enqueue("first", "codex")
    clock.advance(seconds=1)
    _capture(store, "second")
    WriteJobs(store).enqueue("second", "codex")

    drained = write_run.drain(store, _staged_asks("first", "second"), owner="worker-1", limit=1)

    assert [item["session"] for item in drained] == ["first"]
    remaining = WriteJobs(store).list((STATE_QUEUED,))
    assert [job.session for job in remaining] == ["second"]


def test_a_disabled_trace_writes_no_file_and_changes_nothing_else(store):
    store.config.write.jobs.trace_enabled = False
    _capture(store)
    job = WriteJobs(store).enqueue("boundary", "codex")

    payload = write_run.run_job(store, job.id, _ask([]), owner="worker-1")

    assert payload["status"] == "succeeded"
    assert not pathlib.Path(job.trace).exists()


def test_a_traced_run_and_a_plain_run_produce_the_same_distill_output(store, tmp_path):
    plain = store_module.Store(tmp_path / "plain", config=store.config, clock=store.clock)
    plain.init()
    traced = store_module.Store(tmp_path / "traced", config=store.config, clock=store.clock)
    traced.init()
    for target in (plain, traced):
        _capture(target)
    job = WriteJobs(traced).enqueue("boundary", "codex")

    from agent_memory.core import write_trace

    trace = write_trace.WriteTrace(pathlib.Path(job.trace), store.config.write.jobs)
    messages = triggers.backlog(plain.layout, "boundary", Watermark(plain.layout, plain.clock))
    without = distill_module.distill(plain, "boundary", messages, _ask([]))
    with_out = distill_module.distill(traced, "boundary", messages, _ask([]), trace=trace)

    assert with_out.as_dict() == without.as_dict()


def test_drain_leaves_a_backed_off_job_alone_until_it_is_due(store):
    _capture(store)
    queue = WriteJobs(store)
    queue.enqueue("boundary", "codex")
    claimed = queue.claim("worker-a").job
    assert claimed is not None
    failed = queue.fail(claimed, "host unavailable")
    assert failed.state == STATE_FAILED
    calls: list[str] = []

    drained = write_run.drain(store, _ask(calls), owner="worker-b")

    assert drained == []
    assert calls == []
    assert queue.get(claimed.id).state == STATE_FAILED


def test_a_trace_that_cannot_be_written_never_stops_the_run(store):
    _capture(store)
    job = WriteJobs(store).enqueue("boundary", "codex")
    pathlib.Path(job.trace).mkdir(parents=True)

    payload = write_run.run_job(store, job.id, _ask([]), owner="worker-1")

    assert payload["status"] == "succeeded"
    assert payload["distilled"][0]["batches"][0]["written"]
    assert WriteJobs(store).get(job.id).state == STATE_SUCCEEDED


def test_a_crash_between_settle_and_complete_is_recovered_without_a_second_write(store, clock):
    _capture(store)
    job = WriteJobs(store).enqueue("boundary", "codex")
    first: list[str] = []

    def crash_on_complete(self, job, now=None):
        raise OSError("worker died")

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(write_jobs.WriteJobs, "complete", crash_on_complete)
        with pytest.raises(OSError):
            write_run.run_job(store, job.id, _ask(first), owner="worker-a")
    assert len(first) == 1
    names = [record.name for record in store.records()]
    clock.advance(seconds=store.config.write.jobs.lease_seconds + 1)
    second: list[str] = []

    payload = write_run.run_job(store, job.id, _ask(second), owner="worker-b")

    assert payload["reason"] == "already distilled"
    assert second == []
    assert [record.name for record in store.records()] == names
    assert WriteJobs(store).get(job.id).state == STATE_SUCCEEDED


def test_a_running_job_whose_lease_lives_is_skipped_for_another_owner(store):
    _capture(store)
    job = WriteJobs(store).enqueue("boundary", "codex")
    WriteJobs(store).claim("worker-1")

    payload = write_run.run_job(store, job.id, _ask([]), owner="worker-2")

    assert payload["status"] == "skipped"
    assert WriteJobs(store).get(job.id).state == STATE_RUNNING
