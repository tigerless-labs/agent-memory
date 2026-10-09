import pytest
from agent_memory.core.portability import FORMAT_VERSION, import_into


def test_late_malformed_import_entry_preserves_existing_truth(store):
    record = store.record(type="decision", name="import-fixture", abstract="Original fixture")
    before = record.path.read_bytes()
    payload = {
        "format": FORMAT_VERSION,
        "files": [
            {"path": str(record.path.relative_to(store.root)), "text": "replacement"},
            {"path": "decision/incomplete.md"},
        ],
    }
    with pytest.raises(KeyError):
        import_into(store, payload)
    assert record.path.read_bytes() == before
    assert not (store.root / "decision/incomplete.md").exists()
