"""Pipeline-level serialization. Every writer passes through one advisory lock."""

from __future__ import annotations

import contextlib
import pathlib
import time
from collections.abc import Iterator

from . import os_lock
from .config import COORDINATION_LOCK_POLL_SECONDS
from .errors import LockTimeoutError
from .paths import StoreLayout


@contextlib.contextmanager
def _held(
    path: pathlib.Path,
    *,
    shared: bool,
    timeout: float | None,
    poll: float,
    busy_message: str,
) -> Iterator[None]:
    deadline = None if timeout is None else time.monotonic() + timeout
    with path.open("a+", encoding="utf-8") as handle:
        while not os_lock.acquire(handle, shared=shared, blocking=False):
            if deadline is not None and time.monotonic() >= deadline:
                raise LockTimeoutError(busy_message) from None
            time.sleep(poll)
        try:
            yield
        finally:
            os_lock.release(handle)


@contextlib.contextmanager
def file_lock(
    path: pathlib.Path,
    *,
    shared: bool = False,
    timeout: float | None = None,
    poll: float = COORDINATION_LOCK_POLL_SECONDS,
) -> Iterator[None]:
    """Advisory cross-process lock for coordination state, independent of Store writes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with _held(
        path,
        shared=shared,
        timeout=timeout,
        poll=poll,
        busy_message=f"coordination lock busy for {timeout}s",
    ):
        yield


def lock_is_held(path: pathlib.Path) -> bool:
    """Probe an advisory lock. This is paired with a lease; it is not a PID liveness check."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        if not os_lock.acquire(handle, shared=False, blocking=False):
            return True
        os_lock.release(handle)
    return False


@contextlib.contextmanager
def store_lock(layout: StoreLayout) -> Iterator[None]:
    layout.state_dir.mkdir(parents=True, exist_ok=True)
    timeout = layout.config.storage.lock_timeout_seconds
    with _held(
        layout.lock_file,
        shared=False,
        timeout=timeout,
        poll=layout.config.storage.lock_poll_seconds,
        busy_message=f"store lock busy for {timeout}s",
    ):
        yield
