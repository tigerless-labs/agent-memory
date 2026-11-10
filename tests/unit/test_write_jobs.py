"""The durable Write job queue: coalescing, leases, the attempt cap, and quarantine."""

from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import re

import pytest
from agent_memory.adapters import capture
from agent_memory.core import timestamp
from agent_memory.core.dreaming import distill_lock_path
from agent_memory.core.errors import NotFoundError, ValidationError
from agent_memory.core.locking import file_lock
from agent_memory.core.write_jobs import (
    CORRUPT_SUFFIX,
    JOB_SUFFIX,
    STATE_CANCELLED,
    STATE_DEAD,
    STATE_FAILED,
    STATE_QUEUED,
    STATE_RUNNING,
    STATE_SUCCEEDED,
    WriteJobs,
)


def _capture(store, session: str, total: int = 2) -> None:
    capture.capture(
        store,
        session,
        [f"user: the {session} backlog is {number} messages old" for number in range(total)],
        source="pause",
    )


def _enqueue(store, session: str, host: str = "codex"):
    return WriteJobs(store).enqueue(session, host, trigger_source="hook")


def _job_file(store, job_id: str) -> pathlib.Path:
    return store.layout.write_jobs / f"{job_id}{JOB_SUFFIX}"


def test_enqueue_records_the_boundary_target_and_spawn_context(store):
    _capture(store, "boundary", total=2)

    job = _enqueue(store, "boundary")

    assert job.state == STATE_QUEUED
    assert job.session == "boundary"
    assert job.target == 2
    assert job.host == "codex"
    assert job.trigger_source == "hook"
    assert job.attempt == 0
    assert job.max_attempts == store.config.write.jobs.max_attempts
    assert pathlib.Path(job.trace).parent == store.layout.write_traces
    assert _job_file(store, job.id).is_file()
    assert WriteJobs(store).get(job.id) == job


def test_duplicate_boundaries_coalesce_into_one_job_and_extend_its_target(store, clock):
    queue = WriteJobs(store)
    _capture(store, "boundary", total=2)
    first = queue.enqueue("boundary", "codex")
    clock.advance(seconds=1)
    _capture(store, "boundary", total=4)

    second = queue.enqueue("boundary", "claude-code")

    assert second.id == first.id
    assert second.target == 4
    assert second.host == "codex"
    assert list(store.layout.write_jobs.glob("*" + JOB_SUFFIX)) == [_job_file(store, first.id)]


@pytest.mark.parametrize("session", ["../escape", "/tmp/elsewhere", "a/b", "a\\b", ".", "..", ""])
def test_a_session_that_could_leave_the_archive_is_refused(store, session):
    with pytest.raises(ValidationError):
        _enqueue(store, session)
    assert list(store.layout.write_jobs.glob("*" + JOB_SUFFIX)) == []


def test_claim_takes_the_oldest_due_job_first(store, clock):
    queue = WriteJobs(store)
    _capture(store, "first")
    first = queue.enqueue("first", "codex")
    clock.advance(seconds=1)
    _capture(store, "second")
    second = queue.enqueue("second", "codex")

    claimed = queue.claim("worker-1")

    assert claimed.reason == "claimed"
    assert claimed.job.id == first.id
    assert claimed.job.state == STATE_RUNNING
    assert claimed.job.owner == "worker-1"
    assert queue.claim("worker-2").job.id == second.id
    assert queue.claim("worker-3").job is None


def test_a_live_lease_stands_down_and_an_expired_lease_is_reclaimed_only_when_free(store, clock):
    store.config.write.jobs.lease_seconds = 60
    queue = WriteJobs(store)
    _capture(store, "boundary")
    job = queue.enqueue("boundary", "codex")
    claimed = queue.claim("worker-a").job
    assert claimed.id == job.id

    assert queue.claim("worker-b").job is None
    clock.advance(seconds=61)
    with file_lock(distill_lock_path(store, "boundary"), timeout=None):
        standing = queue.claim("worker-b")
        assert standing.job is None
        assert standing.reason == "a worker still holds the distill lock"
        extended = timestamp.parse(queue.get(job.id).lease_until)
    assert extended > timestamp.parse(claimed.lease_until)

    clock.advance(seconds=store.config.write.jobs.lease_seconds + 1)
    reclaimed = queue.claim("worker-b")

    assert reclaimed.reason == "reclaimed"
    assert reclaimed.job.id == job.id
    assert reclaimed.job.attempt == 2
    assert reclaimed.job.owner == "worker-b"


def test_heartbeat_extends_the_lease_of_the_running_job(store, clock):
    store.config.write.jobs.lease_seconds = 100
    queue = WriteJobs(store)
    _capture(store, "boundary")
    queue.enqueue("boundary", "codex")
    claimed = queue.claim("worker-a").job
    assert claimed is not None
    before = timestamp.parse(claimed.lease_until)
    clock.advance(seconds=10)

    beaten = queue.heartbeat(claimed)

    assert timestamp.parse(beaten.lease_until) > before
    assert beaten.state == STATE_RUNNING


def test_heartbeat_leaves_a_job_that_is_not_running_alone(store):
    queue = WriteJobs(store)
    _capture(store, "boundary")
    job = queue.enqueue("boundary", "codex")

    assert queue.heartbeat(job) == job


def test_failure_backs_off_exponentially_then_dies_at_the_attempt_cap(store, clock):
    store.config.write.jobs.max_attempts = 3
    store.config.write.jobs.backoff_base_seconds = 30
    store.config.write.jobs.backoff_max_seconds = 3600
    queue = WriteJobs(store)
    _capture(store, "boundary")
    queue.enqueue("boundary", "codex")

    first = queue.fail(queue.claim("worker").job, "host unavailable")
    assert first.state == STATE_FAILED
    assert first.attempt == 1
    first_delay = (timestamp.parse(first.not_before) - store.clock.now()).total_seconds()

    assert queue.claim("worker").job is None
    clock.advance(seconds=max(60.0, first_delay + 1))
    second = queue.fail(queue.claim("worker").job, "host unavailable again")
    second_delay = (timestamp.parse(second.not_before) - store.clock.now()).total_seconds()

    assert second_delay > first_delay
    assert second_delay >= store.config.write.jobs.backoff_base_seconds

    clock.advance(seconds=max(120.0, second_delay + 1))
    third = queue.fail(queue.claim("worker").job, "host unavailable a third time")

    assert third.state == STATE_DEAD
    assert "unavailable" in third.last_error
    assert third.lease_until == ""


def test_cancel_and_retry_round_trip(store):
    queue = WriteJobs(store)
    _capture(store, "boundary")
    job = queue.enqueue("boundary", "codex")

    cancelled = queue.cancel(job.id)
    assert cancelled.state == STATE_CANCELLED
    retried = queue.retry(job.id)
    assert retried.state == STATE_QUEUED
    assert retried.attempt == 0
    assert retried.not_before == ""
    claimed = queue.claim("worker").job
    assert queue.complete(claimed).state == STATE_SUCCEEDED

    assert queue.cancel(job.id).state == STATE_SUCCEEDED
    with pytest.raises(ValidationError):
        queue.retry(job.id)


def test_listing_filters_by_state(store, clock):
    queue = WriteJobs(store)
    _capture(store, "first")
    first = queue.enqueue("first", "codex")
    clock.advance(seconds=1)
    _capture(store, "second")
    second = queue.enqueue("second", "codex")
    queue.claim("worker")

    assert [job.id for job in queue.list((STATE_QUEUED,))] == [second.id]
    assert [job.id for job in queue.list((STATE_RUNNING,))] == [first.id]
    assert [job.id for job in queue.list()] == [first.id, second.id]


def test_gc_removes_terminal_jobs_and_expired_traces_and_keeps_live_ones(store, clock):
    store.config.write.jobs.retention_days = 7
    queue = WriteJobs(store)
    _capture(store, "finished")
    finished = queue.enqueue("finished", "codex")
    trace = pathlib.Path(finished.trace)
    trace.parent.mkdir(parents=True, exist_ok=True)
    trace.write_text(json.dumps({"event": "run_started"}) + "\n", encoding="utf-8")
    expired = (store.clock.now() - dt.timedelta(days=8)).timestamp()
    os.utime(trace, (expired, expired))
    queue.complete(queue.claim("worker").job)
    _capture(store, "live")
    live = queue.enqueue("live", "codex")

    clock.advance(days=8)
    removed = queue.gc()

    assert removed["jobs"] == 1
    assert removed["traces"] == 1
    assert not _job_file(store, finished.id).exists()
    assert not trace.exists()
    assert queue.get(live.id).state == STATE_QUEUED


def test_a_corrupt_job_file_is_quarantined_and_reported(store):
    queue = WriteJobs(store)
    _capture(store, "boundary")
    job = queue.enqueue("boundary", "codex")
    _job_file(store, job.id).write_text("{not json", encoding="utf-8")

    assert queue.list() == []
    quarantined = _job_file(store, job.id).name + CORRUPT_SUFFIX
    assert queue.quarantined() == (quarantined,)
    assert _job_file(store, job.id).with_name(quarantined).is_file()
    with pytest.raises(NotFoundError):
        queue.get(job.id)


def test_a_job_payload_that_lost_its_shape_is_quarantined_too(store):
    queue = WriteJobs(store)
    _capture(store, "boundary")
    job = queue.enqueue("boundary", "codex")
    _job_file(store, job.id).write_text(json.dumps({"session": "boundary"}), encoding="utf-8")

    assert queue.list() == []
    assert queue.quarantined()


@pytest.mark.parametrize("bad", ["../escape", "/etc/passwd", "", "a/b", "a\\b", ".", ".."])
def test_job_ids_that_could_name_another_file_are_refused(store, bad):
    with pytest.raises(ValidationError):
        WriteJobs(store).get(bad)


def test_job_ids_are_uuid4_hex(store):
    job = _enqueue(store, "boundary")

    assert re.fullmatch(r"[0-9a-f]{32}", job.id)


def test_an_unknown_job_is_reported_as_missing(store):
    with pytest.raises(NotFoundError):
        WriteJobs(store).get("0" * 32)


def test_enqueue_during_a_run_records_a_follow_up_job_instead_of_extending_it(store, clock):
    queue = WriteJobs(store)
    _capture(store, "boundary", total=2)
    running = queue.enqueue("boundary", "codex")
    queue.claim("worker-a")
    clock.advance(seconds=1)
    _capture(store, "boundary", total=4)

    follow_up = queue.enqueue("boundary", "claude-code")

    assert follow_up.id != running.id
    assert follow_up.state == STATE_QUEUED
    assert follow_up.target == 4
    assert follow_up.created_at > running.created_at
    untouched = queue.get(running.id)
    assert untouched.target == 2
    assert untouched.state == STATE_RUNNING


def test_a_follow_up_with_no_fresh_archive_targets_what_the_runner_will_recheck(store, clock):
    queue = WriteJobs(store)
    _capture(store, "boundary", total=2)
    running = queue.enqueue("boundary", "codex")
    queue.claim("worker-a")
    clock.advance(seconds=1)

    follow_up = queue.enqueue("boundary", "codex")

    assert follow_up.id != running.id
    assert follow_up.target == running.target
    assert follow_up.state == STATE_QUEUED


def test_backoff_jitter_is_bounded_and_deterministic_per_attempt(store, clock):
    store.config.write.jobs.backoff_base_seconds = 30
    store.config.write.jobs.backoff_jitter = 0.25
    queue = WriteJobs(store)
    _capture(store, "boundary")
    queue.enqueue("boundary", "codex")

    first = queue.fail(queue.claim("worker").job, "host down")
    delay = (timestamp.parse(first.not_before) - store.clock.now()).total_seconds()
    assert store.config.write.jobs.backoff_base_seconds * 0.75 <= delay
    assert delay <= store.config.write.jobs.backoff_base_seconds * 1.25

    queue.retry(first.id)
    retried = queue.fail(queue.claim("worker").job, "host down again")

    assert (timestamp.parse(retried.not_before) - store.clock.now()).total_seconds() == delay


def test_backoff_jitter_separates_jobs_that_fail_together(store, clock):
    store.config.write.jobs.backoff_base_seconds = 30
    queue = WriteJobs(store)
    for number in range(6):
        session = f"session-{number}"
        _capture(store, session)
        queue.enqueue(session, "codex")

    delays = []
    while queue.list((STATE_QUEUED,)):
        failed = queue.fail(queue.claim("worker").job, "host down")
        delays.append((timestamp.parse(failed.not_before) - store.clock.now()).total_seconds())

    assert len(set(delays)) >= 2


def test_due_count_matches_what_claim_would_take(store, clock):
    queue = WriteJobs(store)
    assert queue.due_count() == 0
    _capture(store, "boundary")
    queue.enqueue("boundary", "codex")
    assert queue.due_count() == 1
    queue.claim("worker")
    assert queue.due_count() == 0

    clock.advance(seconds=store.config.write.jobs.lease_seconds + 1)
    assert queue.due_count() == 1
    with file_lock(distill_lock_path(store, "boundary"), timeout=None):
        assert queue.due_count() == 0
