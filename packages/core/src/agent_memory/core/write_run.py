"""One claimed Write job, end to end: fence, heartbeat, distillation, trace, completion.

The queue decides who runs; this module decides what running means: hold the distill and
maintenance gates, stop early when the watermark already covers the job's target, keep the
lease alive while the reasoner works, and close the job from the outcome. The reasoner stays
a callable supplied from outside the core (Invariant 5).
"""

from __future__ import annotations

import pathlib
import threading
import time

from . import distill as distill_module
from . import triggers, write_trace
from .dreaming import distill_lock_path
from .errors import MemoryStoreError
from .locking import file_lock
from .store import Store
from .watermark import Watermark
from .write_jobs import STATE_RUNNING, WriteJob, WriteJobs
from .write_trace import WriteTrace

REASON_DISTILLED = "distilled"
REASON_SETTLED = "already distilled"
REASON_EMPTY = "nothing to distill"
STATUS_SUCCEEDED = "succeeded"
STATUS_SKIPPED = "skipped"


def run_job(store: Store, job_id: str, ask, *, owner: str = "", transport: str = "") -> dict:
    claimed = WriteJobs(store).claim_id(job_id, owner)
    if claimed.job is None:
        return {"job": job_id, "status": STATUS_SKIPPED, "reason": claimed.reason}
    return _run_claimed(store, claimed.job, ask, transport)


def drain(
    store: Store,
    ask,
    *,
    owner: str = "",
    transport: str = "",
    limit: int | None = None,
) -> list[dict]:
    jobs = WriteJobs(store)
    drained: list[dict] = []
    while limit is None or len(drained) < limit:
        claimed = jobs.claim(owner)
        if claimed.job is None:
            return drained
        drained.append(_run_claimed(store, claimed.job, ask, transport))
    return drained


def _run_claimed(store: Store, job: WriteJob, ask, transport: str) -> dict:
    jobs = WriteJobs(store)
    trace = _trace(store, job)
    if trace is not None:
        trace.run_started(job.id, job.session, job.target, transport)
    started = time.monotonic()
    if _settled(store, job):
        jobs.complete(job)
        if trace is not None:
            trace.run_finished(0, 0, 0, time.monotonic() - started)
        return _payload(job, None, REASON_SETTLED)
    beat = _Heartbeat(store, job)
    try:
        report, reason = _distill_locked(store, job, ask, trace)
    except Exception as error:
        if trace is not None:
            trace.error(type(error).__name__, str(error))
        jobs.fail(job, f"{type(error).__name__}: {error}")
        raise
    finally:
        beat.stop()
    if trace is not None:
        usage = write_trace.last_usage(ask)
        if usage is not None:
            trace.usage(usage)
        trace.run_finished(
            _count(report, lambda batch: len(batch.written)),
            _count(report, lambda batch: len(batch.rejected)),
            _count(report, lambda batch: batch.pending),
            time.monotonic() - started,
        )
    jobs.complete(job)
    return _payload(job, report, reason)


def _distill_locked(store: Store, job: WriteJob, ask, trace: WriteTrace | None):
    with (
        file_lock(distill_lock_path(store, job.session), timeout=None),
        file_lock(store.layout.maintenance_lock, shared=True, timeout=None),
    ):
        if _settled(store, job):
            return None, REASON_SETTLED
        backlog = triggers.backlog(store.layout, job.session, Watermark(store.layout, store.clock))
        if not backlog:
            return None, REASON_EMPTY
        report = distill_module.distill(store, job.session, backlog, ask, trace=trace)
        return report, REASON_DISTILLED


def _trace(store: Store, job: WriteJob) -> WriteTrace | None:
    config = store.config.write.jobs
    if not config.trace_enabled:
        return None
    return WriteTrace(pathlib.Path(job.trace), config, clock=store.clock)


def _settled(store: Store, job: WriteJob) -> bool:
    return Watermark(store.layout, store.clock).read(job.session).distilled >= job.target


def _payload(job: WriteJob, report, reason: str) -> dict:
    return {
        "job": job.id,
        "session": job.session,
        "status": STATUS_SUCCEEDED,
        "reason": reason,
        "distilled": [report.as_dict()] if report is not None else [],
        "trace": job.trace,
    }


def _count(report, measure) -> int:
    if report is None:
        return 0
    return sum(measure(batch) for batch in report.batches)


class _Heartbeat:
    """Keeps the lease of a live run ahead of any parallel claimer until the run ends."""

    def __init__(self, store: Store, job: WriteJob):
        self._interval = store.config.write.jobs.heartbeat_seconds
        self._heartbeat = WriteJobs(store).heartbeat
        self._job = job
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._beat, daemon=True)
        self._thread.start()

    def _beat(self) -> None:
        while not self._stop.wait(self._interval):
            try:
                if self._heartbeat(self._job).state != STATE_RUNNING:
                    return
            except (OSError, MemoryStoreError):
                return

    def stop(self) -> None:
        self._stop.set()
        self._thread.join()
