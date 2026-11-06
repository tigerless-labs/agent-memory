"""The advisory lock must always release its file handle, even on error."""

import pathlib

import pytest
from agent_memory.core.config import Config
from agent_memory.core.errors import LockTimeoutError
from agent_memory.core.locking import file_lock, lock_is_held, store_lock
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


def test_store_lock_releases_after_body_error(tmp_path):
    layout = _layout(tmp_path)
    with pytest.raises(RuntimeError, match="body failed"), store_lock(layout):
        raise RuntimeError("body failed")

    with store_lock(layout):
        pass


def test_shared_coordination_holders_coexist_and_exclude_an_exclusive_one(tmp_path):
    path = tmp_path / "maintenance.lock"
    with file_lock(path, shared=True, timeout=0), file_lock(path, shared=True, timeout=0):
        assert lock_is_held(path)
        with pytest.raises(LockTimeoutError), file_lock(path, timeout=0):
            pass
    assert not lock_is_held(path)


def test_an_exclusive_coordination_holder_excludes_a_shared_one(tmp_path):
    path = tmp_path / "maintenance.lock"
    with (
        file_lock(path, timeout=0),
        pytest.raises(LockTimeoutError),
        file_lock(path, shared=True, timeout=0),
    ):
        pass
    with file_lock(path, shared=True, timeout=0):
        pass


def test_store_lock_times_out_while_another_writer_holds_it(tmp_path):
    layout = _layout(tmp_path)
    layout.config.storage.lock_timeout_seconds = 0
    with store_lock(layout), pytest.raises(LockTimeoutError), store_lock(layout):
        pass
