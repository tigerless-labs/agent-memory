import dataclasses

import pytest
from agent_memory.core import schema
from agent_memory.core.errors import ValidationError
from agent_memory.core.manage import ACTION_CLUSTERED, ACTION_GROUP_MERGED, Manage
from agent_memory.core.recall import Recall


@pytest.fixture(params=[schema.MODE_UPSERT, schema.MODE_ADD_ONLY])
def menu_store(store, request):
    definition = schema.MemorySchema(
        "note", "A sourced note", ("topic", "subject"), group="topic", mode=request.param
    )
    store.schemas.path_for("note").write_text(schema.render(definition), encoding="utf-8")
    return store


@pytest.mark.parametrize("operation", ["cluster", "merge"])
def test_regrouping_preserves_identity_and_evidence(menu_store, clock, operation):
    store = menu_store
    groups = (
        ["account"] * store.config.manage.cluster_min_files
        if operation == "cluster" else ["account", "accounts"]
    )
    store.record(type="fact", name="target", abstract="Independent link target")
    store.archive.append_session(
        "regroup", [f"user: Cache latency note {i}" for i in range(len(groups))]
    )
    for index, group in enumerate(groups):
        store.record(
            type="note", name=f"cache-note-{index}",
            fields={"topic": group, "subject": f"cache-note-{index}"},
            abstract=f"Cache latency note {index}", body=f"Preserve rule {index}.",
            provenance=[f"sessions/regroup#{index}"], links=["target"], create_group=True,
        )
    before = {record.name: record for record in store.records() if record.type == "note"}
    evidence = {name: store.trace(name) for name in before}
    store.record(type="fact", name="index", abstract="Related notes", links=list(before))
    clock.advance(hours=1)

    report = Manage(store).sleep()

    expected = ACTION_CLUSTERED if operation == "cluster" else ACTION_GROUP_MERGED
    assert expected in {action.kind for action in report.actions}
    after = {record.name: record for record in store.records() if record.type == "note"}
    assert after.keys() == before.keys()
    assert any(after[name].path != original.path for name, original in before.items())
    for name, original in before.items():
        moved = after[name]
        assert dataclasses.replace(
            moved, fields=original.fields, path=original.path, updated=original.updated
        ) == original
        assert moved.fields == {**original.fields, "topic": moved.path.parent.name}
        if moved.path != original.path:
            assert not original.path.exists()
        assert store.trace(name) == evidence[name]
        assert evidence[name]
    assert store.find("index").links == list(before)
    store.rebuild_index()
    assert {hit.name for hit in Recall(store).recall("cache latency", log=False)} == set(before)
    assert not {ACTION_CLUSTERED, ACTION_GROUP_MERGED} & {
        action.kind for action in Manage(store).sleep().actions
    }


def test_regroup_rejects_a_stale_source(menu_store):
    store = menu_store
    original = store.record(type="note", name="source", abstract="Original memory")
    store.correct(original.name, body="A concurrent correction")
    before = {path: path.read_bytes() for path in store.layout.truth_files()}

    with pytest.raises(ValidationError, match="changed since"):
        store.regroup(original.name, "new-group", expected_source_hash=original.source_hash)

    assert {path: path.read_bytes() for path in store.layout.truth_files()} == before


def test_overlapping_clusters_keep_the_latest_source_version(menu_store):
    store = menu_store
    count = store.config.manage.cluster_min_files
    for index in range(count + 1):
        store.record(
            type="note", name=f"entry-{index}",
            abstract="Cache latency" if index == count else "Cache latency release rollout",
            body=f"Rule {index}", provenance=[f"Source evidence {index}"],
        )
    before = {record.name: (record.body, record.provenance) for record in store.records()}

    report = Manage(store).sleep()

    moved = [action.target for action in report.actions if action.kind == ACTION_CLUSTERED]
    assert len(moved) > len(set(moved))
    assert {r.name: (r.body, r.provenance) for r in store.records()} == before


def test_regroup_preserves_custom_fields_exactly(menu_store):
    store = menu_store
    original = store.record(type="note", name="source", abstract="Original memory")
    original.fields["custom"] = "  Significant whitespace  "
    store.write(original)

    moved = store.regroup(original.name, "new-group")

    assert moved.fields == {**original.fields, "topic": "new-group"}


def test_regroup_preserves_an_occupied_destination(menu_store):
    store = menu_store
    original = store.record(type="note", name="source", abstract="Original memory")
    destination = original.path.parent.parent / "new-group" / original.path.name
    destination.parent.mkdir()
    destination.write_text("An unindexed file that must survive.\n", encoding="utf-8")
    before = {path: path.read_bytes() for path in store.layout.truth_files()}

    with pytest.raises(ValidationError, match="exists"):
        store.regroup(original.name, "new-group")

    assert {path: path.read_bytes() for path in store.layout.truth_files()} == before


def test_regroup_rolls_back_truth_and_projection(menu_store, monkeypatch):
    store = menu_store
    original = store.record(type="note", name="source", abstract="Orchid source memory")
    before = {path: path.read_bytes() for path in store.layout.truth_files()}
    memory_before = (store.root / "MEMORY.md").read_bytes()
    project = store._project
    failed = False

    def fail_once():
        nonlocal failed
        report = project()
        if not failed:
            failed = True
            raise RuntimeError("injected projection failure")
        return report

    monkeypatch.setattr(store, "_project", fail_once)
    with pytest.raises(RuntimeError, match="injected projection failure"):
        store.regroup(original.name, "new-group")

    assert {path: path.read_bytes() for path in store.layout.truth_files()} == before
    assert (store.root / "MEMORY.md").read_bytes() == memory_before
    assert store.find(original.name).path == original.path
    assert {hit.name for hit in Recall(store).recall("orchid", log=False)} == {original.name}


def test_regroup_preserves_historical_validity(menu_store):
    store = menu_store
    original = store.record(type="note", name="source", abstract="Historical memory")
    original = store.delete(original.name)

    moved = store.regroup(original.name, "new-group")

    assert not moved.is_active()
    assert moved.invalid_at == original.invalid_at
    assert moved.valid_from == original.valid_from
    assert not original.path.exists()
    assert store.records() == []


def test_regroup_rejects_a_system_group(store):
    original = store.record(type="event", name="source", abstract="Dated event")
    before = original.path.read_bytes()

    with pytest.raises(ValidationError, match="menu"):
        store.regroup(original.name, "new-group")

    assert original.path.read_bytes() == before
