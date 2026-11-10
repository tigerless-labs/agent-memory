"""Durable record of every requested boundary distillation.

A boundary hands its backlog to a detached worker; the hand-off is a job here, not a process
that may vanish. State lives beside the watermarks and the pending queue — one file per job,
written atomically under one advisory lock — so a worker that dies leaves something the next
lifecycle event can resume. Losing the queue costs retries, never memories.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
import os
import pathlib
import random
import re
import tempfile
import uuid
from collections.abc import Sequence

from . import sessions, timestamp
from .config import STATE_JSON_INDENT, WriteJobsConfig
from .errors import FieldError, NotFoundError, ValidationError
from .locking import file_lock, lock_is_held
from .redaction import redact
from .store import Store
from .watermark import Watermark

STATE_QUEUED = "queued"
STATE_RUNNING = "running"
STATE_SUCCEEDED = "succeeded"
STATE_FAILED = "failed"
STATE_DEAD = "dead"
STATE_CANCELLED = "cancelled"
STATES = (
    STATE_QUEUED,
    STATE_RUNNING,
    STATE_SUCCEEDED,
    STATE_FAILED,
    STATE_DEAD,
    STATE_CANCELLED,
)
RETRYABLE_STATES = (STATE_QUEUED, STATE_FAILED)
TERMINAL_STATES = (STATE_SUCCEEDED, STATE_DEAD, STATE_CANCELLED)
JOB_SUFFIX = ".json"
CORRUPT_SUFFIX = ".corrupt"
TRACE_SUFFIX = ".jsonl"
JOB_ID_LENGTH = 32
_ID = re.compile(r"[0-9a-f]+")
BACKOFF_FACTOR = 2
REMOVED_JOBS = "jobs"
REMOVED_TRACES = "traces"


@dataclasses.dataclass(frozen=True)
class WriteJob:
    id: str
    session: str
    target: int
    state: str
    attempt: int
    max_attempts: int
    created_at: str
    updated_at: str
    not_before: str
    lease_until: str
    owner: str
    host: str
    trigger_source: str
    last_error: str
    trace: str

    def as_dict(self) -> dict[str, object]:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class JobClaim:
    job: WriteJob | None
    reason: str


JobList = list[WriteJob]


class WriteJobs:
    """The queue. Every mutation holds one advisory lock; every file write is atomic."""

    def __init__(self, store: Store):
        self._store = store
        self._quarantined: list[str] = []

    def enqueue(self, session: str, host: str, trigger_source: str = "") -> WriteJob:
        sessions.session_path(self._store.layout, session)
        with self._lock():
            now = self._now()
            target = self._consumed(session)
            jobs = self._load_all()
            open_job = next(
                (job for job in jobs if job.session == session and job.state == STATE_QUEUED),
                None,
            )
            if open_job is not None:
                return self._store_job(
                    dataclasses.replace(
                        open_job,
                        target=max(open_job.target, target),
                        updated_at=timestamp.render(now),
                    )
                )
            return self._store_job(
                self._new_job(session, host, trigger_source, target, now),
            )

    def _new_job(
        self, session: str, host: str, trigger_source: str, target: int, now: dt.datetime
    ) -> WriteJob:
        rendered = timestamp.render(now)
        job_id = uuid.uuid4().hex
        return WriteJob(
            id=job_id,
            session=session,
            target=target,
            state=STATE_QUEUED,
            attempt=0,
            max_attempts=self._config.max_attempts,
            created_at=rendered,
            updated_at=rendered,
            not_before="",
            lease_until="",
            owner="",
            host=host,
            trigger_source=trigger_source,
            last_error="",
            trace=str(self.trace_path(job_id)),
        )

    def claim(self, owner: str, now: dt.datetime | None = None) -> JobClaim:
        with self._lock():
            moment = now or self._now()
            jobs = self._load_all()
            due = sorted(
                (job for job in jobs if self._due(job, moment)),
                key=lambda job: (job.created_at, job.id),
            )
            if due:
                return JobClaim(self._take(due[0], owner, moment), "claimed")
            stand_down = ""
            expired = sorted(
                (job for job in jobs if job.state == STATE_RUNNING),
                key=lambda job: (job.lease_until, job.id),
            )
            for job in expired:
                expires = _instant(job.lease_until)
                if expires is not None and moment < expires:
                    stand_down = "another worker holds a live lease"
                    continue
                if lock_is_held(self._distill_lock(job.session)):
                    self._store_job(self._with_lease(job, moment))
                    stand_down = "a worker still holds the distill lock"
                    continue
                return JobClaim(self._take(job, owner, moment), "reclaimed")
            return JobClaim(None, stand_down or "nothing due")

    def claim_id(self, job_id: str, owner: str, now: dt.datetime | None = None) -> JobClaim:
        with self._lock():
            job = self._read(job_id)
            moment = now or self._now()
            if job.state == STATE_RUNNING:
                expires = _instant(job.lease_until)
                if expires is not None and moment < expires and job.owner != owner:
                    return JobClaim(None, "another owner holds a live lease")
                if job.owner != owner and lock_is_held(self._distill_lock(job.session)):
                    self._store_job(self._with_lease(job, moment))
                    return JobClaim(None, "a worker still holds the distill lock")
                return JobClaim(self._take(job, owner, moment), "claimed")
            if job.state in RETRYABLE_STATES:
                if not self._due(job, moment):
                    return JobClaim(None, "not due yet")
                return JobClaim(self._take(job, owner, moment), "claimed")
            return JobClaim(None, f"job is {job.state}")

    def heartbeat(self, job: WriteJob, now: dt.datetime | None = None) -> WriteJob:
        with self._lock():
            current = self._read(job.id)
            if current.state != STATE_RUNNING:
                return current
            return self._store_job(self._with_lease(current, now or self._now()))

    def complete(self, job: WriteJob, now: dt.datetime | None = None) -> WriteJob | None:
        with self._lock():
            current = self._read(job.id)
            if current.state not in (STATE_RUNNING, STATE_SUCCEEDED):
                return None
            return self._store_job(
                dataclasses.replace(
                    current,
                    state=STATE_SUCCEEDED,
                    lease_until="",
                    owner="",
                    last_error="",
                    updated_at=timestamp.render(now or self._now()),
                )
            )

    def fail(self, job: WriteJob, error: str, now: dt.datetime | None = None) -> WriteJob | None:
        with self._lock():
            current = self._read(job.id)
            if current.state != STATE_RUNNING or current.owner != job.owner:
                return None
            moment = now or self._now()
            exhausted = current.attempt >= current.max_attempts
            return self._store_job(
                dataclasses.replace(
                    current,
                    state=STATE_DEAD if exhausted else STATE_FAILED,
                    lease_until="",
                    owner="",
                    last_error=redact(str(error).strip())[: self._config.error_max_chars],
                    not_before="" if exhausted else self._backoff(current, moment),
                    updated_at=timestamp.render(moment),
                )
            )

    def cancel(self, job_id: str, now: dt.datetime | None = None) -> WriteJob:
        with self._lock():
            current = self._read(job_id)
            if current.state not in (STATE_QUEUED, STATE_RUNNING):
                return current
            return self._store_job(
                dataclasses.replace(
                    current,
                    state=STATE_CANCELLED,
                    lease_until="",
                    owner="",
                    updated_at=timestamp.render(now or self._now()),
                )
            )

    def retry(self, job_id: str, now: dt.datetime | None = None) -> WriteJob:
        with self._lock():
            current = self._read(job_id)
            if current.state == STATE_QUEUED:
                return current
            if current.state not in (STATE_FAILED, STATE_DEAD, STATE_CANCELLED):
                raise ValidationError(
                    [FieldError("job", f"a {current.state} job cannot be retried")]
                )
            return self._store_job(
                dataclasses.replace(
                    current,
                    state=STATE_QUEUED,
                    attempt=0,
                    not_before="",
                    lease_until="",
                    owner="",
                    last_error="",
                    updated_at=timestamp.render(now or self._now()),
                )
            )

    def get(self, job_id: str) -> WriteJob:
        with self._lock():
            return self._read(job_id)

    def list(self, states: Sequence[str] | None = None) -> JobList:
        unknown = sorted(set(states or ()) - set(STATES))
        if unknown:
            raise ValidationError(
                [
                    FieldError(
                        "state",
                        f"unknown job state: {', '.join(unknown)}; use one of {', '.join(STATES)}",
                    )
                ]
            )
        with self._lock():
            found = self._load_all()
        if states:
            found = [job for job in found if job.state in states]
        return sorted(found, key=lambda job: (job.created_at, job.id))

    def gc(self, now: dt.datetime | None = None) -> dict[str, int]:
        with self._lock():
            moment = now or self._now()
            horizon = moment - dt.timedelta(days=self._config.retention_days)
            removed_jobs = 0
            for job in self._load_all():
                if job.state not in TERMINAL_STATES:
                    continue
                updated = _instant(job.updated_at)
                if updated is None or updated >= horizon:
                    continue
                self._job_path(job.id).unlink(missing_ok=True)
                removed_jobs += 1
            removed_traces = 0
            folder = self._store.layout.write_traces
            if folder.is_dir():
                for path in folder.glob("*" + TRACE_SUFFIX):
                    if not _expired_trace(path, moment, self._config.retention_days):
                        continue
                    path.unlink(missing_ok=True)
                    removed_traces += 1
            return {REMOVED_JOBS: removed_jobs, REMOVED_TRACES: removed_traces}

    def due_count(self, now: dt.datetime | None = None) -> int:
        with self._lock():
            moment = now or self._now()
            count = 0
            for job in self._load_all():
                if job.state in RETRYABLE_STATES and self._due(job, moment):
                    count += 1
                elif job.state == STATE_RUNNING:
                    expires = _instant(job.lease_until)
                    if (expires is None or moment >= expires) and not lock_is_held(
                        self._distill_lock(job.session)
                    ):
                        count += 1
            return count

    def quarantined(self) -> tuple[str, ...]:
        return tuple(self._quarantined)

    def _lock(self):
        return file_lock(
            self._store.layout.write_job_lock,
            timeout=self._store.config.storage.lock_timeout_seconds,
        )

    @property
    def _config(self) -> WriteJobsConfig:
        return self._store.config.write.jobs

    def _now(self) -> dt.datetime:
        return self._store.clock.now()

    def _consumed(self, session: str) -> int:
        return Watermark(self._store.layout, self._store.clock).read(session).consumed

    def _distill_lock(self, session: str) -> pathlib.Path:
        digest = hashlib.sha256(session.encode("utf-8")).hexdigest()
        return self._store.layout.distill_locks / f"{digest}.lock"

    def _due(self, job: WriteJob, moment: dt.datetime) -> bool:
        if job.state not in RETRYABLE_STATES:
            return False
        earliest = _instant(job.not_before)
        return earliest is None or moment >= earliest

    def _take(self, job: WriteJob, owner: str, moment: dt.datetime) -> WriteJob:
        return self._store_job(
            dataclasses.replace(
                job,
                state=STATE_RUNNING,
                attempt=job.attempt + 1,
                lease_until=timestamp.render(
                    moment + dt.timedelta(seconds=self._config.lease_seconds)
                ),
                owner=owner,
                updated_at=timestamp.render(moment),
            )
        )

    def _with_lease(self, job: WriteJob, moment: dt.datetime) -> WriteJob:
        return dataclasses.replace(
            job,
            lease_until=timestamp.render(moment + dt.timedelta(seconds=self._config.lease_seconds)),
            updated_at=timestamp.render(moment),
        )

    def _backoff(self, job: WriteJob, moment: dt.datetime) -> str:
        delay = min(
            self._config.backoff_base_seconds * BACKOFF_FACTOR ** max(0, job.attempt - 1),
            self._config.backoff_max_seconds,
        )
        spread = random.Random(f"{job.id}:{job.attempt}").uniform(-1.0, 1.0)
        jittered = delay * (1.0 + spread * self._config.backoff_jitter)
        return timestamp.render(moment + dt.timedelta(seconds=jittered))

    def trace_path(self, job_id: str) -> pathlib.Path:
        return self._store.layout.write_traces / f"{job_id}{TRACE_SUFFIX}"

    def _job_path(self, job_id: str) -> pathlib.Path:
        return self._store.layout.write_jobs / f"{job_id}{JOB_SUFFIX}"

    def _store_job(self, job: WriteJob) -> WriteJob:
        path = self._job_path(job.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        rendered = json.dumps(job.as_dict(), indent=STATE_JSON_INDENT, sort_keys=True) + "\n"
        with tempfile.NamedTemporaryFile(
            "w", dir=path.parent, delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(rendered)
            staged = pathlib.Path(tmp.name)
        try:
            os.replace(staged, path)
        finally:
            staged.unlink(missing_ok=True)
        return job

    def _read(self, job_id: str) -> WriteJob:
        if not _ID.fullmatch(job_id) or len(job_id) != JOB_ID_LENGTH:
            raise ValidationError([FieldError("job", f"not a job id: {job_id!r}")])
        path = self._job_path(job_id)
        if not path.is_file():
            raise NotFoundError(f"no Write job {job_id}")
        return self._with_trace_path(
            _job_from_payload(json.loads(path.read_text(encoding="utf-8")), path)
        )

    def _load_all(self) -> JobList:
        folder = self._store.layout.write_jobs
        self._quarantined = []
        if not folder.is_dir():
            return []
        found: list[WriteJob] = []
        for path in sorted(folder.glob("*" + JOB_SUFFIX)):
            try:
                found.append(
                    self._with_trace_path(
                        _job_from_payload(json.loads(path.read_text(encoding="utf-8")), path)
                    )
                )
            except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
                quarantined = path.with_name(path.name + CORRUPT_SUFFIX)
                os.replace(path, quarantined)
                self._quarantined.append(quarantined.name)
        return found

    def _with_trace_path(self, job: WriteJob) -> WriteJob:
        return dataclasses.replace(job, trace=str(self.trace_path(job.id)))


def _expired_trace(path: pathlib.Path, moment: dt.datetime, retention_days: float) -> bool:
    try:
        modified = dt.datetime.fromtimestamp(path.stat().st_mtime, tz=dt.UTC)
    except OSError:
        return False
    return moment - modified >= dt.timedelta(days=retention_days)


def _job_from_payload(payload: object, path: pathlib.Path) -> WriteJob:
    if not isinstance(payload, dict):
        raise ValueError("job payload must be an object")
    job = WriteJob(
        id=str(payload["id"]),
        session=str(payload["session"]),
        target=int(payload["target"]),
        state=str(payload["state"]),
        attempt=int(payload["attempt"]),
        max_attempts=int(payload["max_attempts"]),
        created_at=str(payload["created_at"]),
        updated_at=str(payload["updated_at"]),
        not_before=str(payload["not_before"]),
        lease_until=str(payload["lease_until"]),
        owner=str(payload["owner"]),
        host=str(payload["host"]),
        trigger_source=str(payload["trigger_source"]),
        last_error=str(payload["last_error"]),
        trace=str(payload["trace"]),
    )
    if job.state not in STATES or job.id != path.stem:
        raise ValueError("job payload lost its shape")
    return job


def _instant(value: str) -> dt.datetime | None:
    if not value.strip():
        return None
    try:
        return timestamp.parse(value)
    except ValueError:
        return None
