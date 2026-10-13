"""Pipeline-level serialization. Every writer passes through one advisory lock."""

from __future__ import annotations

import contextlib
import time
from collections.abc import Iterator

from . import portlock
from .errors import LockTimeoutError
from .paths import StoreLayout


@contextlib.contextmanager
def store_lock(layout: StoreLayout) -> Iterator[None]:
    layout.state_dir.mkdir(parents=True, exist_ok=True)
    timeout = layout.config.storage.lock_timeout_seconds
    poll = layout.config.storage.lock_poll_seconds
    deadline = time.monotonic() + timeout
    with layout.lock_file.open("a+", encoding="utf-8") as handle:
        while True:
            try:
                portlock.lock_exclusive(handle, blocking=False)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise LockTimeoutError(f"store lock busy for {timeout}s") from None
                time.sleep(poll)
        try:
            yield
        finally:
            portlock.unlock(handle)
