import pytest
from agent_memory.core.migrate import migrate, needs_migration


@pytest.mark.parametrize(
    "kind,fields",
    [
        ("reference", {"source": "general", "subject": "resource"}),
        ("experience", {"topic": "general", "subject": "lesson"}),
    ],
)
def test_current_store_does_not_need_or_lose_truth_on_migration(store, kind, fields):
    record = store.record(type=kind, fields=fields, abstract="Current layout fixture")
    before = record.path.read_bytes()
    assert not needs_migration(store.root)
    assert migrate(store.root).moved == ()
    assert record.path.read_bytes() == before
    assert not needs_migration(store.root)
