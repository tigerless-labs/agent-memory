"""Pipeline-level serialization. Every writer passes through one advisory lock."""

from __future__ import annotations

import contextlib
import os
import time
from collections.abc import Iterator
from typing import IO

from .errors import LockTimeoutError
from .paths import StoreLayout

if os.name == "nt":
    import msvcrt

    def _acquire(handle: IO[str]) -> None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)

    def _release(handle: IO[str]) -> None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _acquire(handle: IO[str]) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _release(handle: IO[str]) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


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
                _acquire(handle)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise LockTimeoutError(f"store lock busy for {timeout}s") from None
                time.sleep(poll)
        try:
            yield
        finally:
            _release(handle)
    finally:
        handle.close()
