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


def test_move_failure_preserves_active_and_retry_succeeds(store, monkeypatch):
    old = memory(store, provenance=["original evidence"])
    source = old.path
    before = source.read_bytes()
    target = store.layout.archived_memories / source.relative_to(store.root)
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
    assert source.read_bytes() == before
    assert MemoryRecord.from_text(source.read_text()).is_active()
    assert not target.exists()
    assert evidence.exists()
    assert store.read(old.name).text == old.body
    assert store.delete(old.name).path == target
    assert not source.exists()
    assert_isolated(store, old.name)


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


def test_destination_collision_preserves_both_copies(store):
    old = memory(store)
    before = old.path.read_bytes()
    target = store.layout.archived_memories / old.path.relative_to(store.root)
    target.parent.mkdir(parents=True)
    target.write_text("existing historical evidence")
    with pytest.raises(FileExistsError):
        store.delete(old.name)
    assert target.read_text() == "existing historical evidence"
    assert old.path.read_bytes() == before
    assert MemoryRecord.from_text(old.path.read_text()).is_active()
    assert store.read(old.name).text == old.body


def test_failed_atomic_status_write_preserves_active_original(store, monkeypatch):
    old = memory(store)
    before = old.path.read_bytes()
    archive_path = store.layout.archived_memories / old.path.relative_to(store.root)
    original = pathlib.Path.replace

    def fail(path, target):
        if target == archive_path:
            raise OSError("status write failed")
        return original(path, target)

    with monkeypatch.context() as patch:
        patch.setattr(pathlib.Path, "replace", fail)
        with pytest.raises(OSError, match="status write failed"):
            store.delete(old.name)
    assert old.path.read_bytes() == before
    assert not archive_path.exists()
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


def test_supersede_move_failure_keeps_predecessor_and_no_successor(store, monkeypatch):
    old = memory(store)
    before = old.path.read_bytes()
    original = pathlib.Path.rename

    def fail(path, target):
        if path == old.path:
            raise OSError("archive move failed")
        return original(path, target)

    with monkeypatch.context() as patch:
        patch.setattr(pathlib.Path, "rename", fail)
        with pytest.raises(OSError, match="archive move failed"):
            store.record(
                type="fact", name="new-memory", abstract="New fact", supersedes=old.name
            )
    assert old.path.read_bytes() == before
    assert store.read(old.name).record.is_active()
    assert store.find("new-memory") is None
    assert store.record(
        type="fact", name="new-memory", abstract="New fact", supersedes=old.name
    ).is_active()
    assert_isolated(store, old.name)


def test_correct_move_failure_keeps_original_and_successor(store, monkeypatch):
    old = memory(store)
    successor = memory(store, name="new-memory")
    before = old.path.read_bytes()
    original = pathlib.Path.rename

    def fail(path, target):
        if path == old.path:
            raise OSError("archive move failed")
        return original(path, target)

    with monkeypatch.context() as patch:
        patch.setattr(pathlib.Path, "rename", fail)
        with pytest.raises(OSError, match="archive move failed"):
            store.correct(old.name, supersede_with=successor.name)
    assert old.path.read_bytes() == before
    assert store.read(old.name).record.is_active()
    assert store.read(successor.name).record.is_active()


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


def test_temporal_scope_uses_original_memory_location(store, clock):
    old = memory(store)
    scope = str(old.path.parent.relative_to(store.root))
    moment = clock.timestamp()
    clock.advance(days=1)
    store.delete(old.name)
    assert old.name in {h.name for h in Recall(store).recall("Quasar", scope=scope, as_of=moment)}


def test_manage_duplicate_archives_only_invalid_copy_and_rebuild_keeps_active(store):
    from agent_memory.core.manage import ACTION_DUPLICATE_MERGED, Manage

    original = memory(store, name="first-copy")
    duplicate = memory(store, name="second-copy")
    original_path = original.path
    duplicate_path = duplicate.path

    report = Manage(store).sleep()
    assert ACTION_DUPLICATE_MERGED in {action.kind for action in report.actions}
    archived = store.find(duplicate.name)
    assert archived.status == "invalid"
    assert archived.superseded_by == original.name
    assert archived.path == store.layout.archived_memories / duplicate_path.relative_to(store.root)
    assert not duplicate_path.exists()
    assert original_path.exists()
    assert store.read(original.name).record.is_active()

    store.rebuild_index()
    Manage(store).sleep()
    assert original_path.exists()
    assert store.find(original.name).path == original_path
    assert store.find(duplicate.name).path == archived.path
    assert duplicate.name not in {hit.name for hit in Recall(store).recall("Quasar")}
