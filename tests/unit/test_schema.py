"""ADR-008 — a type is a schema file; the tree is a function of type and key, not a choice."""

import pytest
from agent_memory.core import placement, schema
from agent_memory.core.errors import ValidationError
from agent_memory.core.recall import Recall
from agent_memory.core.record import STATUS_INVALID


def _schema(store, **overrides):
    base = {"type": "decision", "description": "A choice", "key": ("project", "subject"),
            "group": "project"}
    base.update(overrides)
    return schema.MemorySchema(**base)


def test_the_factory_set_is_written_once_and_loads_back_unchanged(store):
    loaded = store.schemas.load()
    assert set(loaded) == {item.type for item in schema.FACTORY}
    for item in schema.FACTORY:
        assert schema.parse(schema.render(item)) == item


def test_a_group_must_come_from_a_system_or_menu_field(store):
    with pytest.raises(ValidationError) as raised:
        schema.validate(_schema(store, key=("subject",), group="subject"), store.config)
    assert "group" in {error.field for error in raised.value.errors}


def test_a_group_must_be_one_of_the_key_fields(store):
    with pytest.raises(ValidationError):
        schema.validate(_schema(store, key=("subject",), group="project"), store.config)


def test_a_schema_file_declaring_the_wrong_type_name_is_rejected(store):
    path = store.schemas.path_for("mislabelled")
    path.write_text(schema.render(_schema(store, type="decision")), encoding="utf-8")
    store.schemas._schemas = None
    with pytest.raises(ValidationError):
        store.schemas.load()


def test_the_same_key_resolves_to_the_same_path_whatever_the_wording(store):
    first = store.record(
        type="decision", fields={"project": "agent-memory", "subject": "BM25 core"},
        abstract="Use BM25 as the retrieval core",
    )
    second = store.record(
        type="decision", fields={"project": "agent-memory", "subject": "bm25 core"},
        abstract="BM25 is the retrieval core",
    )
    assert first.path == second.path
    assert first.path.relative_to(store.root).parts[:2] == ("decision", "agent-memory")


def test_a_free_field_never_becomes_a_directory(store):
    written = store.record(
        type="decision",
        fields={"project": "agent-memory", "subject": "../etc/passwd"},
        abstract="A subject that tries to climb out",
    )
    parts = written.path.relative_to(store.root).parts
    assert len(parts) == len(("decision", "agent-memory", "file"))
    assert ".." not in written.name


def test_a_menu_group_must_already_exist_unless_creation_is_requested(store):
    with pytest.raises(ValidationError) as raised:
        store.record(
            type="preference", fields={"topic": "coffee", "subject": "milk"},
            abstract="Prefers oat milk",
        )
    assert "topic" in {error.field for error in raised.value.errors}
    created = store.record(
        type="preference", fields={"topic": "coffee", "subject": "milk"},
        abstract="Prefers oat milk", create_group=True,
    )
    assert created.path.parent.name == "coffee"
    again = store.record(
        type="preference", fields={"topic": "Coffee", "subject": "sugar"},
        abstract="Takes no sugar",
    )
    assert again.path.parent == created.path.parent


def test_a_missing_menu_group_lands_in_the_default_group(store):
    written = store.record(type="preference", fields={"subject": "milk"}, abstract="Oat milk")
    assert written.path.parent.name == store.config.storage.default_group


def test_system_fields_are_filled_by_the_store_not_the_writer(store):
    decision = store.record(type="decision", fields={"subject": "x"}, abstract="Decided x")
    assert decision.fields["project"] == store.config.storage.default_project
    event = store.record(
        type="event", fields={"subject": "trip"}, abstract="Went on a trip",
        valid_from="2023-05-30",
    )
    assert event.path.parent.name == "2023-05"


def test_add_only_types_never_overwrite_an_existing_file(store):
    first = store.record(type="event", fields={"subject": "trip"}, abstract="First trip")
    second = store.record(type="event", fields={"subject": "trip"}, abstract="Second trip")
    assert first.path != second.path
    assert first.path.exists() and second.path.exists()


def test_depth_is_capped_by_config(store):
    store.config.storage.max_depth = len(("type", "file"))
    with pytest.raises(ValidationError):
        store.record(type="decision", fields={"subject": "too deep"}, abstract="Too deep")


def test_reserved_segment_names_are_made_portable(config):
    assert placement.portable_segment("CON", config) != "con"
    assert placement.portable_segment("nul", config).startswith("nul")


def test_supersede_invalidates_the_predecessor_at_the_successors_valid_from(store):
    old = store.record(type="fact", fields={"subject": "timeout"}, abstract="Timeout is 30s",
                       valid_from="2026-01-01")
    new = store.record(
        type="fact", fields={"subject": "timeout v2"}, abstract="Timeout is 60s",
        valid_from="2026-02-01", supersedes=old.name,
    )
    predecessor = store.find(old.name)
    assert predecessor.status == STATUS_INVALID
    assert predecessor.invalid_at == new.valid_from
    assert predecessor.superseded_by == new.name
    assert predecessor.path.exists()


def test_as_of_before_the_replacement_returns_the_predecessor(store):
    old = store.record(type="fact", fields={"subject": "timeout"}, abstract="Timeout is 30s",
                       valid_from="2026-01-01")
    store.record(
        type="fact", fields={"subject": "timeout v2"}, abstract="Timeout is 60s",
        valid_from="2026-02-01", supersedes=old.name,
    )
    before = [hit.name for hit in Recall(store).recall("timeout", as_of="2026-01-15")]
    after = [hit.name for hit in Recall(store).recall("timeout", as_of="2026-02-15")]
    assert before == [old.name]
    assert old.name not in after


def test_an_in_place_write_may_reword_but_not_change_the_fact(store):
    store.record(type="fact", fields={"subject": "timeout"}, abstract="Timeout is 30s",
                 body="The queue timeout is thirty seconds.")
    reworded = store.record(type="fact", fields={"subject": "timeout"},
                            abstract="Queue timeout: 30 seconds")
    assert reworded.body == "The queue timeout is thirty seconds."
    with pytest.raises(ValidationError) as raised:
        store.record(type="fact", fields={"subject": "timeout"}, abstract="Timeout is 60s",
                     body="The queue timeout is sixty seconds.")
    assert "body" in {error.field for error in raised.value.errors}


def test_delete_marks_invalid_and_keeps_the_file(store):
    written = store.record(type="fact", fields={"subject": "gone"}, abstract="Soon gone")
    removed = store.delete(written.name)
    assert removed.status == STATUS_INVALID
    assert removed.invalid_at
    assert removed.path.exists()
    assert written.name not in {record.name for record in store.records()}
    assert written.name in {record.name for record in store.records(include_invalid=True)}
    assert not Recall(store).recall("soon gone")


def test_rebuild_equivalence_holds_with_invalid_files_present(store):
    old = store.record(type="fact", fields={"subject": "timeout"}, abstract="Timeout is 30s",
                       valid_from="2026-01-01")
    store.record(type="fact", fields={"subject": "timeout v2"}, abstract="Timeout is 60s",
                 valid_from="2026-02-01", supersedes=old.name)
    store.delete(store.record(type="fact", fields={"subject": "x"}, abstract="Deleted x").name)
    queries = [("timeout", None), ("timeout", "2026-01-15"), ("deleted x", None)]
    before = {q: [h.name for h in Recall(store).recall(q[0], as_of=q[1])] for q in queries}
    store.layout.index_db.unlink()
    store.rebuild_index()
    after = {q: [h.name for h in Recall(store).recall(q[0], as_of=q[1])] for q in queries}
    assert after == before


def test_a_four_domain_store_migrates_into_the_schema_layout(tmp_path, clock):
    from agent_memory.core import frontmatter, migrate
    from agent_memory.core.store import Store

    root = tmp_path / "legacy"
    (root / "project").mkdir(parents=True)
    (root / "archive" / "retired" / "user").mkdir(parents=True)
    (root / "project" / "drain-window.md").write_text(
        frontmatter.render(
            {"name": "drain-window", "abstract": "Drain window is 90s", "type": "fact",
             "status": "stale", "created": "2026-01-01", "updated": "2026-01-02",
             "author": "old", "links": [], "provenance": []},
            "Body.",
        ),
        encoding="utf-8",
    )
    (root / "archive" / "retired" / "user" / "old-pref.md").write_text(
        frontmatter.render(
            {"name": "old-pref", "abstract": "Used to like tea", "type": "preference",
             "status": "retired", "created": "2026-01-01", "updated": "2026-01-03",
             "author": "old", "links": [], "provenance": []},
            "",
        ),
        encoding="utf-8",
    )
    (root / "config.toml").write_text(
        '[storage]\ndomains = ["user", "project", "reference", "experience"]\n', encoding="utf-8"
    )
    assert migrate.needs_migration(root)
    report = migrate.migrate(root)
    assert not migrate.needs_migration(root)
    store = Store(root, clock=clock)
    active = {record.name: record for record in store.records()}
    everything = {record.name: record for record in store.records(include_invalid=True)}
    assert active["drain-window"].path.relative_to(root).parts[:2] == ("fact", "project")
    assert everything["old-pref"].status == STATUS_INVALID
    assert everything["old-pref"].path.relative_to(root).parts[:2] == ("preference", "user")
    assert "old-pref" in report.invalidated
    assert not (root / "project").exists()
