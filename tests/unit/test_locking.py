"""The advisory lock must always release its file handle, even on error."""

import pathlib

import pytest
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


def test_store_lock_releases_after_body_error(tmp_path):
    layout = _layout(tmp_path)
    with pytest.raises(RuntimeError, match="body failed"), store_lock(layout):
        raise RuntimeError("body failed")

    with store_lock(layout):
        pass
