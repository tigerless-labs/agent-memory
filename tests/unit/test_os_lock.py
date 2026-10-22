"""One lock primitive with the same shared/exclusive semantics on POSIX and Windows."""

import threading
import time

import pytest
from agent_memory.core import os_lock


@pytest.fixture
def lock_path(tmp_path):
    path = tmp_path / "coordination.lock"
    path.touch()
    return path


def _open(path):
    return path.open("a+", encoding="utf-8")


@pytest.mark.parametrize(
    ("first_shared", "second_shared", "coexist"),
    [(False, False, False), (False, True, False), (True, False, False), (True, True, True)],
)
def test_contention_across_handles_follows_reader_writer_semantics(
    lock_path, first_shared, second_shared, coexist
):
    with _open(lock_path) as first, _open(lock_path) as second:
        assert os_lock.acquire(first, shared=first_shared, blocking=False)
        assert os_lock.acquire(second, shared=second_shared, blocking=False) is coexist
        os_lock.release(first)
        if coexist:
            os_lock.release(second)


def test_release_makes_the_lock_available_again(lock_path):
    with _open(lock_path) as first, _open(lock_path) as second:
        assert os_lock.acquire(first, shared=False, blocking=False)
        os_lock.release(first)
        assert os_lock.acquire(second, shared=False, blocking=False)
        os_lock.release(second)


def test_blocking_acquire_waits_for_the_holder(lock_path):
    released = threading.Event()
    with _open(lock_path) as holder:
        assert os_lock.acquire(holder, shared=False, blocking=False)

        def _release_later():
            time.sleep(0.2)
            released.set()
            os_lock.release(holder)

        thread = threading.Thread(target=_release_later)
        thread.start()
        with _open(lock_path) as waiter:
            assert os_lock.acquire(waiter, shared=False, blocking=True)
            assert released.is_set()
            os_lock.release(waiter)
        thread.join()


def test_a_held_lock_never_blocks_ordinary_reads_or_appends(lock_path):
    lock_path.write_text("existing\n", encoding="utf-8")
    with _open(lock_path) as holder:
        assert os_lock.acquire(holder, shared=False, blocking=False)
        with lock_path.open("a", encoding="utf-8") as appender:
            appender.write("appended\n")
        assert lock_path.read_text(encoding="utf-8") == "existing\nappended\n"
        os_lock.release(holder)
