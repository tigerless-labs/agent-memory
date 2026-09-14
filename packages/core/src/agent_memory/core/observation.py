"""Optional bounded exam evidence, separate from usage telemetry and memory truth.

No inputs or return values are modified. Missing/partial evidence is never proof of
no calls. The harness owns the directory; standalone library use is silent.
"""

from __future__ import annotations

import contextvars
import fcntl
import hashlib
import json
import os
import pathlib
import re
import time
import uuid

ENV = "AGENT_MEMORY_OBSERVATION_DIR"
ATTEMPT_ENV = "AGENT_MEMORY_OBSERVATION_ATTEMPT"
REVISION = "read-observation-v2"
MAX_BYTES = 2 * 1024 * 1024
MAX_TEXT = 8192
MAX_ITEMS = 128
DIRECTORY_MODE = 0o700
FILE_MODE = 0o600
HOST_TEXT_LIMIT = 65536
HOST_EVENT_BYTES = 1024 * 1024
TOOL_EVENT_BYTES = 65536
LIMIT_MARKER_RESERVE = 128
_call = contextvars.ContextVar("memory_observation_call", default="")
_secret = re.compile(r"(?i)(bearer\s+|(?:api[_-]?key|token|password|secret)\s*[=:]\s*)[^\s,\"']+")


def bounded(value, text_limit: int = MAX_TEXT):
    """Bound every variable-length field; retain hashes/counts for incomplete evidence."""
    if isinstance(value, str):
        clean = _secret.sub(r"\1[REDACTED]", value)
        if len(clean) <= text_limit:
            return clean
        return {
            "excerpt": clean[:text_limit],
            "chars": len(clean),
            "truncated": True,
            "sha256": hashlib.sha256(clean.encode()).hexdigest(),
        }
    if isinstance(value, (list, tuple)):
        items = [bounded(item, text_limit) for item in value[:MAX_ITEMS]]
        if len(value) > MAX_ITEMS:
            return {"items": items, "count": len(value), "truncated": True}
        return items
    if isinstance(value, dict):
        return {key: bounded(item, text_limit) for key, item in value.items()}
    return value


def emit(kind: str, *, directory: str | None = None, channel: str = "tools", **data) -> None:
    target = directory or os.environ.get(ENV)
    if not target:
        return
    try:
        path = pathlib.Path(target)
        path.mkdir(parents=True, exist_ok=True, mode=DIRECTORY_MODE)
        event = bounded(
            {
                "revision": REVISION,
                "kind": kind,
                "at_ns": time.time_ns(),
                "call_id": _call.get(),
                "attempt_id": os.environ.get(ATTEMPT_ENV, ""),
                **data,
            },
            text_limit=HOST_TEXT_LIMIT if channel == "host" else MAX_TEXT,
        )
        encoded = (json.dumps(event, ensure_ascii=True) + "\n").encode()
        if len(encoded) > (HOST_EVENT_BYTES if channel == "host" else TOOL_EVENT_BYTES):
            encoded = (
                json.dumps(
                    {
                        "revision": REVISION,
                        "kind": kind,
                        "call_id": _call.get(),
                        "truncated": True,
                        "bytes": len(encoded),
                        "sha256": hashlib.sha256(encoded).hexdigest(),
                    }
                )
                + "\n"
            ).encode()
        fd = os.open(path / f"{channel}.jsonl", os.O_CREAT | os.O_APPEND | os.O_WRONLY, FILE_MODE)
        with os.fdopen(fd, "ab") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            size = os.fstat(handle.fileno()).st_size
            if size >= MAX_BYTES or (path / f"{channel}.limited").exists():
                return
            if size + len(encoded) > MAX_BYTES - LIMIT_MARKER_RESERVE:
                handle.write(b'{"kind":"evidence_limit","truncated":true}\n')
                # A separate marker prevents later small events pretending completeness.
                (path / f"{channel}.limited").touch(mode=FILE_MODE)
            else:
                handle.write(encoded)
    except (OSError, TypeError, ValueError):
        # Observation failure must not change tool results or ranking.
        return


def invoke(handler, store, args):
    if not os.environ.get(ENV):
        return handler(store, args)
    token = _call.set(uuid.uuid4().hex)
    arguments = {
        key: value
        for key, value in vars(args).items()
        if key
        in {
            "command",
            "query",
            "name",
            "level",
            "deep",
            "limit",
            "scope",
            "as_of",
            "json",
            "agent",
            "pointer",
        }
    }
    emit("tool_start", arguments=arguments)
    try:
        result = handler(store, args)
        emit("tool_return", command=args.command, result=result)
        return result
    except Exception as error:
        emit("tool_error", command=args.command, error_type=type(error).__name__)
        raise
    finally:
        _call.reset(token)
