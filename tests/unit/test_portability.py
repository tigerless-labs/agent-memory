"""Export/import round-trip, and the path-traversal guard on import."""

import pathlib

import pytest

from agent_memory.core import portability
from agent_memory.core.clock import FrozenClock
from agent_memory.core.config import Config
from agent_memory.core.store import Store


@pytest.fixture
def source_store(tmp_path):
    config = Config.default()
    clock = FrozenClock(__import__("datetime").datetime(2026, 1, 15, 9, 0, tzinfo=__import__("datetime").UTC))
    store = Store(tmp_path / "src-store", config=config, clock=clock, agent="test")
    store.init()
    store.record(
        abstract="A memory about queues",
        type="fact",
        domain="project",
        name="queue-fact",
    )
    return store


@pytest.fixture
def target_store(tmp_path):
    config = Config.default()
    clock = FrozenClock(__import__("datetime").datetime(2026, 1, 15, 9, 0, tzinfo=__import__("datetime").UTC))
    store = Store(tmp_path / "dst-store", config=config, clock=clock, agent="test")
    store.init()
    return store


def test_export_round_trip_preserves_content(source_store, target_store):
    payload = portability.export_store(source_store, include_archive=False)
    written = portability.import_into(target_store, payload)
    assert written >= 1
    names = [record.name for record in target_store.records()]
    assert "queue-fact" in names


def test_write_export_creates_file(source_store, tmp_path):
    out = tmp_path / "export.json"
    portability.write_export(source_store, out, include_archive=False)
    assert out.exists()
    assert out.stat().st_size > 0


def test_import_refuses_path_traversal(target_store):
    """An export payload with a relative path that escapes the store root
    must be rejected rather than writing outside the store."""
    payload = {
        "format": portability.FORMAT_VERSION,
        "files": [
            {"path": "../../etc/malicious", "text": "should not land here"},
        ],
    }
    with pytest.raises(ValueError, match="path traversal"):
        portability.import_into(target_store, payload)


def test_import_refuses_absolute_path_outside_store(target_store):
    """An absolute path in the export payload must not write outside the store."""
    payload = {
        "format": portability.FORMAT_VERSION,
        "files": [
            {"path": "/tmp/escape", "text": "should not land here"},
        ],
    }
    with pytest.raises(ValueError, match="path traversal"):
        portability.import_into(target_store, payload)


def test_import_allows_valid_relative_paths(target_store):
    """Normal relative paths within the store must work as before."""
    payload = {
        "format": portability.FORMAT_VERSION,
        "files": [
            {"path": "project/valid-record.md", "text": "---\nname: valid\n---\nbody"},
        ],
    }
    written = portability.import_into(target_store, payload)
    assert written == 1
