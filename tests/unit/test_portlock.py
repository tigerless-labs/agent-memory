"""Advisory locking is portable: it round-trips on every platform, accepts a
file object or a raw descriptor, and never disturbs the descriptor offset."""

import importlib
import os

from agent_memory.core import portlock


def test_exclusive_lock_round_trip_blocking(tmp_path):
    with (tmp_path / "lock").open("a+", encoding="utf-8") as handle:
        portlock.lock_exclusive(handle, blocking=True)
        portlock.unlock(handle)


def test_exclusive_lock_round_trip_nonblocking(tmp_path):
    with (tmp_path / "lock").open("a+", encoding="utf-8") as handle:
        portlock.lock_exclusive(handle, blocking=False)
        portlock.unlock(handle)


def test_lock_accepts_raw_descriptor_and_preserves_offset(tmp_path):
    path = tmp_path / "lock"
    path.write_bytes(b"abcdef")
    fd = os.open(path, os.O_RDWR)
    try:
        os.lseek(fd, 3, os.SEEK_SET)
        portlock.lock_exclusive(fd, blocking=True)
        assert os.lseek(fd, 0, os.SEEK_CUR) == 3
        portlock.unlock(fd)
        assert os.lseek(fd, 0, os.SEEK_CUR) == 3
    finally:
        os.close(fd)


def test_core_lock_modules_import_on_every_platform():
    """Regression: the lock holders must not import a POSIX-only module at module
    load time, or the whole package fails to import on Windows."""
    assert importlib.import_module("agent_memory.core.locking")
    assert importlib.import_module("agent_memory.core.observation")
