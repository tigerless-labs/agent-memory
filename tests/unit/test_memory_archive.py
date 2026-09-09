import pathlib

import pytest
from agent_memory.core import context, injection
from agent_memory.core.errors import NotFoundError, ValidationError
from agent_memory.core.recall import Recall
from agent_memory.core.record import MemoryRecord


def memory(store, name="old-memory", **kwargs):
    return store.record(
        type="fact", name=name, abstract="Quasar queue timeout", body="Old fact", **kwargs
    )


def assert_isolated(store, name):
    for level in ("abstract", "outline", "full"):
        with pytest.raises(NotFoundError):
            store.read(name, level=level)
    with pytest.raises(NotFoundError):
        store.trace(name)
    assert name not in {hit.name for hit in Recall(store).recall("Quasar")}
    assert name not in context.build(store, "Quasar").names
    assert name not in injection.payload(store)


def test_archive_lifecycle_history_and_rebuild(store, clock):
    old = memory(store)
    source = old.path
    assert store.read(old.name).text == old.body
    assert old.name in {hit.name for hit in Recall(store).recall("Quasar")}
    moment = clock.timestamp()
    clock.advance(days=1)
    invalid = store.delete(old.name)
    assert invalid.path == store.layout.archived_memories / source.relative_to(store.root)
    assert not source.exists()
    assert invalid.path.exists()
    assert invalid.status == "invalid"
    assert_isolated(store, old.name)
    for _ in range(2):
        store.rebuild_index()
        assert store.read(old.name, include_invalid=True).text == old.body
        assert old.name in {h.name for h in Recall(store).recall("Quasar", as_of=moment)}
        assert old.body in context.build(store, "Quasar", as_of=moment).text
    before = invalid.path.read_bytes()
    clock.advance(days=1)
    assert store.delete(old.name).path.read_bytes() == before


def test_move_failure_is_invalid_retryable_and_keeps_raw(store, monkeypatch):
    old = memory(store, provenance=["original evidence"])
    source = old.path
    evidence = store.archive.provenance_of(old.name)[0]
    original = pathlib.Path.rename

    def fail(path, target):
        if path == source:
            raise OSError("archive move failed")
        return original(path, target)

    with monkeypatch.context() as patch:
        patch.setattr(pathlib.Path, "rename", fail)
        with pytest.raises(OSError, match="archive move failed"):
            store.delete(old.name)
    assert not MemoryRecord.from_text(source.read_text()).is_active()
    assert evidence.exists()
    assert_isolated(store, old.name)
    assert store.delete(old.name).path.is_relative_to(store.layout.archived_memories)


def test_projection_failure_does_not_leak_and_retry_repairs_index(store, monkeypatch):
    old = memory(store)

    def fail():
        raise OSError("index unavailable")

    with monkeypatch.context() as patch:
        patch.setattr(store._indexer, "sync", fail)
        with pytest.raises(OSError, match="index unavailable"):
            store.delete(old.name)
    assert_isolated(store, old.name)
    assert store.find(old.name).path.is_relative_to(store.layout.archived_memories)
    store.delete(old.name)
    assert_isolated(store, old.name)


def test_shared_and_missing_raw_survive_invalidation(store):
    store.archive.append_session("shared", ["user: quasar evidence"])
    old = memory(store, provenance=["sessions/shared#0-0", "sessions/missing#0-0"])
    other = memory(store, "other-memory", provenance=["sessions/shared#0-0"])
    before = store.trace(other.name)
    store.delete(old.name)
    assert store.trace(other.name) == before
    assert store.trace(old.name, include_invalid=True) == before
    assert store.find(old.name).provenance == old.provenance


def test_legacy_invalid_is_filtered_and_archived_on_retry(store):
    old = memory(store)
    text = old.path.read_text().replace("status: active", "status: invalid")
    text = text.replace("invalid_at: null", "invalid_at: 2026-01-15")
    old.path.write_text(text)
    assert_isolated(store, old.name)
    assert store.delete(old.name).path.is_relative_to(store.layout.archived_memories)


@pytest.mark.parametrize("links", [["missing"], ["source"]])
def test_invalid_relationship_additions_are_rejected(store, links):
    memory(store, "source")
    with pytest.raises(ValidationError):
        store.correct("source", links=links)
    assert store.find("source").links == []


def test_relationship_replacement_and_invalid_endpoints(store):
    memory(store, "source")
    memory(store, "target")
    assert store.correct("source", links=["target"]).links == ["target"]
    assert store.correct("source", links=[]).links == []
    store.delete("target")
    with pytest.raises(ValidationError):
        store.correct("source", links=["target"])
    with pytest.raises(ValidationError):
        store.correct("source", supersede_with="target")
    with pytest.raises(ValidationError):
        store.correct("target", body="resurrection")


def test_destination_collision_preserves_both_copies(store):
    old = memory(store)
    target = store.layout.archived_memories / old.path.relative_to(store.root)
    target.parent.mkdir(parents=True)
    target.write_text("existing historical evidence")
    with pytest.raises(FileExistsError):
        store.delete(old.name)
    assert target.read_text() == "existing historical evidence"
    assert not MemoryRecord.from_text(old.path.read_text()).is_active()
    assert_isolated(store, old.name)


def test_failed_atomic_status_write_preserves_active_original(store, monkeypatch):
    old = memory(store)
    before = old.path.read_bytes()
    original = pathlib.Path.replace

    def fail(path, target):
        if target == old.path:
            raise OSError("status write failed")
        return original(path, target)

    with monkeypatch.context() as patch:
        patch.setattr(pathlib.Path, "replace", fail)
        with pytest.raises(OSError, match="status write failed"):
            store.delete(old.name)
    assert old.path.read_bytes() == before
    assert store.read(old.name).text == old.body
    assert list(old.path.parent.iterdir()) == [old.path]
    store.delete(old.name)
    assert_isolated(store, old.name)


def test_stale_manage_write_cannot_resurrect_archived_memory(store):
    stale = memory(store)
    store.delete(stale.name)
    stale.weight = store.config.weight.ceiling
    with pytest.raises(ValidationError):
        store.write(stale)
    assert not stale.path.exists()
    assert_isolated(store, stale.name)


def test_supersede_and_archive_retry_preserve_successor_and_original_time(store, clock):
    old = memory(store)
    clock.advance(days=1)
    new = store.record(type="fact", name="new-memory", abstract="New fact", supersedes=old.name)
    invalid = store.find(old.name)
    clock.advance(days=1)
    again = store.delete(old.name)
    assert again.superseded_by == new.name
    assert again.invalid_at == invalid.invalid_at
    assert again.path == invalid.path
    assert store.read(new.name).record.is_active()


def test_missing_optional_legacy_fields_remain_compatible(store):
    old = memory(store)
    text = "\n".join(
        line
        for line in old.path.read_text().splitlines()
        if not line.startswith(("status:", "provenance:", "valid_from:"))
    )
    old.path.write_text(text)
    assert store.read(old.name).text == old.body
    store.delete(old.name)
    assert store.read(old.name, include_invalid=True).record.provenance == []


def test_existing_historical_links_survive_other_metadata_updates(store):
    target = memory(store, "target")
    source = memory(store, "source", links=[target.name])
    store.delete(target.name)
    updated = store.correct(source.name, abstract="Updated quasar wording")
    assert updated.links == [target.name]
    assert store.correct(source.name, links=[]).links == []


def test_archive_rejects_active_memory_and_repeated_archive_is_noop(store):
    old = memory(store)
    with pytest.raises(ValidationError):
        store.archive.archive_memory(old)
    archived = store.delete(old.name)
    before = archived.path.read_bytes()
    assert store.archive.archive_memory(archived) == archived.path
    assert archived.path.read_bytes() == before


def test_invalid_evidence_does_not_become_an_automatic_redistill_request(store):
    from agent_memory.core.manage import ACTION_REDISTILL_REQUESTED, Manage

    store.archive.append_session("shared", ["user: quasar evidence"])
    old = memory(store, provenance=["sessions/shared#0-0"])
    store.delete(old.name)
    for _ in range(store.config.manage.raw_hit_min):
        Recall(store).recall("quasar", deep=True)
    assert ACTION_REDISTILL_REQUESTED not in {
        action.kind for action in Manage(store).sleep().actions
    }


def test_unlink_does_not_delete_target_or_evidence(store):
    target = memory(store, "target", provenance=["original evidence"])
    source = memory(store, "source", links=[target.name])
    before = target.path.read_bytes()
    store.correct(source.name, links=[])
    assert store.read(target.name).text == target.body
    assert target.path.read_bytes() == before
    assert store.archive.provenance_of(target.name)


def test_temporal_scope_uses_original_memory_location(store, clock):
    old = memory(store)
    scope = str(old.path.parent.relative_to(store.root))
    moment = clock.timestamp()
    clock.advance(days=1)
    store.delete(old.name)
    assert old.name in {h.name for h in Recall(store).recall("Quasar", scope=scope, as_of=moment)}
