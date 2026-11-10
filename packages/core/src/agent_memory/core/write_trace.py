"""The per-run Write trace: one append-only JSONL record of what a distillation did.

The trace is runtime state, not memory truth: it exists so an operator can answer "what did
that run send, call, write, and refuse" without replaying it. Every string passes redaction,
bodies are digested unless explicitly enabled, and the file stops growing at its bound.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib

from . import timestamp
from .clock import Clock
from .config import WriteJobsConfig
from .redaction import redact

EVENT_STARTED = "run_started"
EVENT_BATCH = "batch"
EVENT_ROUND = "round"
EVENT_TOOL_CALL = "tool_call"
EVENT_OPERATIONS = "operations"
EVENT_REPAIR = "repair"
EVENT_USAGE = "usage"
EVENT_ERROR = "error"
EVENT_FINISHED = "run_finished"
EVENT_TRUNCATED = "truncated"
KEY_AT = "at"
KEY_EVENT = "event"
KEY_DIGEST = "digest"
KEY_LENGTH = "length"
KEY_ARGUMENTS = "arguments"
ENCODING = "utf-8"


class WriteTrace:
    def __init__(
        self,
        path: pathlib.Path,
        config: WriteJobsConfig,
        clock: Clock | None = None,
    ):
        self._path = path
        self._config = config
        self._clock = clock or Clock()
        self._stopped = False
        self._torn = False
        try:
            size = self._path.stat().st_size
        except OSError:
            size = 0
        if size:
            try:
                with self._path.open("rb") as handle:
                    handle.seek(-1, os.SEEK_END)
                    self._torn = handle.read(1) != b"\n"
            except OSError:
                self._stopped = True

    def run_started(self, job_id: str, session: str, target: int, reasoner: str) -> None:
        self._write(
            EVENT_STARTED,
            {"job": job_id, "session": session, "target": target, "reasoner": reasoner},
        )

    def batch(self, pointer: str, chars: int, slots: int) -> None:
        self._write(EVENT_BATCH, {"pointer": pointer, "chars": chars, "slots": slots})

    def round(self, number: int) -> None:
        self._write(EVENT_ROUND, {"round": number})

    def tool_call(self, name: str, arguments: object) -> None:
        rendered = _rendered(arguments)
        event = {
            "name": name,
            KEY_DIGEST: hashlib.sha256(rendered.encode(ENCODING)).hexdigest(),
            KEY_LENGTH: len(rendered),
        }
        if self._config.trace_bodies:
            event[KEY_ARGUMENTS] = arguments
        self._write(EVENT_TOOL_CALL, event)

    def operations(self, applied: list[str], rejected: list[dict[str, object]]) -> None:
        self._write(EVENT_OPERATIONS, {"applied": applied, "rejected": rejected})

    def repair(self, number: int, leftovers: int) -> None:
        self._write(EVENT_REPAIR, {"round": number, "leftovers": leftovers})

    def usage(self, usage: object) -> None:
        self._write(EVENT_USAGE, {"usage": usage})

    def error(self, kind: str, message: str) -> None:
        self._write(EVENT_ERROR, {"kind": kind, "message": message})

    def run_finished(self, written: int, rejected: int, pending: int, seconds: float) -> None:
        self._write(
            EVENT_FINISHED,
            {"written": written, "rejected": rejected, "pending": pending, "seconds": seconds},
        )

    def _write(self, event: str, payload: dict[str, object]) -> None:
        if self._stopped:
            return
        try:
            size = self._path.stat().st_size if self._path.exists() else 0
            if size >= self._config.trace_max_bytes:
                self._stop()
                return
            self._path.parent.mkdir(parents=True, exist_ok=True)
            line = json.dumps(
                {
                    KEY_AT: timestamp.render(self._clock.now()),
                    KEY_EVENT: event,
                    **_redacted_payload(payload),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            self._append(line)
        except OSError:
            self._stopped = True

    def _stop(self) -> None:
        self._stopped = True
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._append(
                json.dumps(
                    {
                        KEY_AT: timestamp.render(self._clock.now()),
                        KEY_EVENT: EVENT_TRUNCATED,
                    }
                )
            )
        except OSError:
            return

    def _append(self, line: str) -> None:
        with self._path.open("a", encoding=ENCODING) as handle:
            if self._torn:
                handle.write("\n")
                self._torn = False
            handle.write(line + "\n")


def last_usage(reasoner: object) -> object:
    """The usage a reasoner chose to expose, or None; the attribute protocol is optional."""
    return getattr(reasoner, "last_usage", None)


def read(path: pathlib.Path, config: WriteJobsConfig) -> list[dict[str, object]]:
    """The events one trace holds, bounded by the size cap and tolerant of a torn last line."""
    events: list[dict[str, object]] = []
    consumed = 0
    try:
        with path.open("r", encoding=ENCODING) as handle:
            for line in handle:
                consumed += len(line.encode(ENCODING))
                if consumed > config.trace_max_bytes:
                    break
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    events.append(_redacted_payload(payload))
    except OSError:
        return events
    return events


def _rendered(arguments: object) -> str:
    try:
        return json.dumps(arguments, sort_keys=True, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(arguments)


def _redacted_payload(payload: dict[str, object]) -> dict[str, object]:
    return {key: _redacted(value) for key, value in payload.items()}


def _redacted(value: object) -> object:
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {str(key): _redacted(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redacted(item) for item in value]
    if isinstance(value, tuple):
        return [_redacted(item) for item in value]
    return value
