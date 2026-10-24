from agent_memory.core.recall import Recall


def test_invalid_external_edit_cannot_keep_old_cached_knowledge(store):
    record = store.record(
        abstract="Unique aquarium knowledge", type="fact", body="aquarium", name="aquarium"
    )
    assert record.path is not None
    original = record.path.read_text(encoding="utf-8")
    invalid = original.replace("abstract: Unique aquarium knowledge", "abstract: ")
    assert invalid != original
    record.path.write_text(invalid, encoding="utf-8")
    report = store.sync_index()
    assert report.unreadable
    assert Recall(store).recall("aquarium", log=False) == []
    assert record.path.read_text(encoding="utf-8") == invalid
    record.path.write_text(original, encoding="utf-8")
    store.sync_index()
    assert [hit.name for hit in Recall(store).recall("aquarium", log=False)] == ["aquarium"]
