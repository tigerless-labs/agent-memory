"""The advisory lock must always release its file handle, even on error."""

import pathlib

import pytest

from agent_memory.core.clock import FrozenClock
from agent_memory.core.config import Config
from agent_memory.core.locking import store_lock
from agent_memory.core.paths import StoreLayout


def _layout(tmp_path: pathlib.Path) -> StoreLayout:
    config = Config.default()
    layout = StoreLayout(root=tmp_path / "store", config=config)
    layout.ensure()
    return layout


def test_store_lock_acquires_and_releases(tmp_path):
    layout = _layout(tmp_path)
    entered = False
    with store_lock(layout):
        entered = True
    assert entered
    # Lock file exists after first use
    assert layout.lock_file.exists()


def test_store_lock_creates_state_dir_if_missing(tmp_path):
    config = Config.default()
    layout = StoreLayout(root=tmp_path / "new-store", config=config)
    # state_dir does not exist yet
    assert not layout.state_dir.exists()
    with store_lock(layout):
        pass
    assert layout.state_dir.exists()
    assert layout.lock_file.exists()


def test_store_lock_handle_is_closed_after_use(tmp_path):
    """After the context manager exits, the file handle must be closed.

    The old code opened the handle before a try/finally, so an unexpected
    error between open() and the try block would leak it. Using a `with`
    statement guarantees the handle is closed on every exit path.
    """
    layout = _layout(tmp_path)
    with store_lock(layout):
        pass
    # Try to acquire the lock again — this would deadlock if the handle
    # were still held by the first acquisition (on the same fd).
    with store_lock(layout):
        pass


def test_lock_file_is_opened_with_explicit_encoding(tmp_path):
    """The lock file open() call must specify encoding to avoid relying
    on the locale default, even though the handle is used only for flock()."""
    import inspect
    source = inspect.getsource(store_lock)
    assert "encoding=" in source, "lock file open() should specify encoding"
