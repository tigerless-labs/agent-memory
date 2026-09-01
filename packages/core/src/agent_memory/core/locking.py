"""Pipeline-level serialization. Every writer passes through one advisory lock."""

from __future__ import annotations

import contextlib
import fcntl
import time
from collections.abc import Iterator

from .errors import LockTimeoutError
from .paths import StoreLayout


@contextlib.contextmanager
def store_lock(layout: StoreLayout) -> Iterator[None]:
    layout.state_dir.mkdir(parents=True, exist_ok=True)
    timeout = layout.config.storage.lock_timeout_seconds
    poll = layout.config.storage.lock_poll_seconds
    deadline = time.monotonic() + timeout
    handle = layout.lock_file.open("a+")
    try:
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise LockTimeoutError(f"store lock busy for {timeout}s") from None
                time.sleep(poll)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()
