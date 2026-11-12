"""One turn, many memories.

A host pays a turn per tool call, so a per-record write API taxes exactly the hosts with the
tightest turn budgets — measured at 13x spread in capture across three hosts on identical
instructions. Batching removes the tax without changing what a memory is.
"""

import pytest
from agent_memory.core.errors import NotFoundError, ValidationError
from agent_memory.core.recall import Recall

SPECS = [
    {
        "abstract": "Sister gave a snake plant on 2023-03-04",
        "type": "fact",
        "name": "snake-plant-gift",
    },
    {
        "abstract": "Basil needs afternoon shade and well-draining soil",
        "type": "fact",
        "name": "basil-care",
    },
    {
        "abstract": "Fern pest treatment uses neem oil weekly",
        "type": "procedure",
        "name": "fern-neem-oil",
        "body": "# Steps\nSpray weekly until the scale is gone.\n",
    },
]


def test_a_batch_writes_every_record_in_one_call(store):
    written = store.record_many(SPECS)
    assert [record.name for record in written.written] == [spec["name"] for spec in SPECS]
    assert written.rejected == []
    assert {record.name for record in store.records()} == {spec["name"] for spec in SPECS}


def test_a_batch_leaves_the_same_store_as_records_written_one_by_one(tmp_path, config, clock):
    from agent_memory.core.store import Store

    batched = Store(tmp_path / "batched", config=config, clock=clock, agent="t")
    batched.init()
    batched.record_many(SPECS)

    sequential = Store(tmp_path / "sequential", config=config, clock=clock, agent="t")
    sequential.init()
    for spec in SPECS:
        sequential.record(**spec)

    def shape(store):
        return sorted(
            (record.name, record.abstract, record.type, record.body) for record in store.records()
        )

    assert shape(batched) == shape(sequential)
    query = "snake plant basil fern"
    assert {hit.name for hit in Recall(batched).recall(query)} == {
        hit.name for hit in Recall(sequential).recall(query)
    }


def test_one_bad_record_does_not_cost_the_good_ones(store):
    specs = [SPECS[0], {"abstract": "", "type": "fact"}, SPECS[1]]
    result = store.record_many(specs)

    assert [record.name for record in result.written] == [SPECS[0]["name"], SPECS[1]["name"]]
    assert len(result.rejected) == 1
    assert result.rejected[0].index == 1
    assert "abstract" in {error.field for error in result.rejected[0].errors}


def test_a_rejection_says_which_record_and_which_field(store):
    result = store.record_many([{"abstract": "wrong type", "type": "nonsense"}])
    assert result.written == []
    rejected = result.rejected[0]
    assert rejected.index == 0
    assert "type" in {error.field for error in rejected.errors}
    assert "fact" in rejected.as_dict()["errors"][0]["reason"]


def test_an_entirely_invalid_batch_still_reports_rather_than_raising(store):
    result = store.record_many([{"abstract": "", "type": ""}])
    assert result.written == []
    assert result.rejected
    assert store.records() == []


def test_a_batch_can_supersede_within_itself(store):
    store.record(abstract="Worn twice as of 2023-04-01", type="fact", name="converse-count-april")
    result = store.record_many(
        [
            {
                "abstract": "Worn six times as of 2023-05-20",
                "type": "fact",
                "name": "converse-count-may",
                "supersedes": "converse-count-april",
            }
        ]
    )
    assert result.written
    assert store.find("converse-count-april").superseded_by == "converse-count-may"
    assert "converse-count-april" not in {r.name for r in store.records() if r.is_active()}


def test_the_batch_path_is_the_same_write_path(store, monkeypatch):
    """Invariant 2: batching must not become a second way into the store."""
    calls = []
    original = type(store)._project
    monkeypatch.setattr(type(store), "_project", lambda self: calls.append(1) or original(self))
    store.record_many(SPECS)
    assert len(calls) == 1, "a batch projects once, not once per record"


def test_a_batch_does_not_rescan_the_truth_tree_per_record(store, monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("a batch scanned the truth tree per record")

    monkeypatch.setattr(type(store), "_scan_for", unexpected)

    result = store.record_many(SPECS)

    assert [record.name for record in result.written] == [spec["name"] for spec in SPECS]


def test_a_batch_still_finds_a_record_the_projection_does_not_know(store):
    written = store.record(
        abstract="Orchid original",
        type="fact",
        name="orchid",
        fields={"project": "shop"},
    )
    store.layout.index_db.unlink()

    result = store.record_many(
        [
            {
                "abstract": "Orchid after the move",
                "type": "fact",
                "name": "orchid",
                "fields": {"project": "billing"},
            }
        ]
    )

    assert result.written
    moved = store.find("orchid")
    assert moved.abstract == "Orchid after the move"
    assert moved.path.parent.name == "billing"
    assert moved.path != written.path
    assert not written.path.exists()


def test_a_batch_resolves_a_name_it_wrote_earlier(store):
    result = store.record_many(
        [
            {"abstract": "First orchid note", "type": "fact", "name": "orchid"},
            {"abstract": "Second orchid note", "type": "fact", "name": "orchid"},
        ]
    )

    assert [record.name for record in result.written] == ["orchid", "orchid"]
    assert len([path for path in store.layout.truth_files() if path.stem == "orchid"]) == 1
    assert store.find("orchid").abstract == "Second orchid note"


def test_an_empty_batch_is_not_an_error(store):
    result = store.record_many([])
    assert result.written == []
    assert result.rejected == []


def test_a_batch_rejects_a_malformed_spec_rather_than_guessing(store):
    result = store.record_many([{"not_a_field": 1}])
    assert result.written == []
    assert "not_a_field" in str(result.rejected[0].errors)


def test_one_stray_key_costs_its_own_memory_and_not_the_batch(store):
    result = store.record_many(
        [
            {"type": "fact", "fields": {"subject": "kept"}, "abstract": "This one is written"},
            {
                "type": "fact",
                "fields": {"subject": "strayed"},
                "abstract": "This one carries a key the store does not know",
                "group": "invented",
            },
            {"type": "fact", "fields": {"subject": "also kept"}, "abstract": "So is this one"},
        ]
    )
    assert [record.name for record in result.written] == ["kept", "also-kept"]
    assert [item.index for item in result.rejected] == [1]
    assert "group" in str(result.rejected[0].errors)


@pytest.mark.parametrize("weight", ["oops", "", [], {}, True, "nan", "inf", "-inf"])
def test_invalid_weights_reject_only_their_own_item(store, weight):
    result = store.record_many([SPECS[0], {**SPECS[2], "weight": weight}, SPECS[1]])

    assert [record.name for record in result.written] == [SPECS[0]["name"], SPECS[1]["name"]]
    assert [item.index for item in result.rejected] == [1]
    assert {error.field for error in result.rejected[0].errors} == {"weight"}
    assert {hit.name for hit in Recall(store).recall("snake plant basil")} == {
        record.name for record in result.written
    }


def test_a_numeric_weight_string_keeps_its_value(store):
    written = store.record(**SPECS[0], weight=str(store.config.weight.initial))
    assert written.weight == store.config.weight.initial


def test_a_single_invalid_weight_uses_the_same_validation_boundary(store):
    with pytest.raises(ValidationError) as failure:
        store.record(**SPECS[0], weight="oops")
    assert {error.field for error in failure.value.errors} == {"weight"}
    assert not store.records()


@pytest.mark.parametrize(
    "valid_from",
    [
        "not-a-date",
        "2026-01-15T09:00:00",
        "0001-01-01T00:00:00+01:00",
        "9999-12-31T23:59:59-01:00",
    ],
)
def test_invalid_event_dates_reject_only_their_own_item(store, valid_from):
    result = store.record_many(
        [
            SPECS[0],
            {**SPECS[2], "type": "event", "valid_from": valid_from},
            SPECS[1],
        ]
    )
    assert [record.name for record in result.written] == [SPECS[0]["name"], SPECS[1]["name"]]
    assert [item.index for item in result.rejected] == [1]
    assert {error.field for error in result.rejected[0].errors} == {"valid_from"}


@pytest.mark.parametrize("spec", [None, [], ["type"], "fact", 1])
def test_non_object_specs_reject_only_their_own_item(store, spec):
    result = store.record_many([SPECS[0], spec, SPECS[1]])
    assert [record.name for record in result.written] == [SPECS[0]["name"], SPECS[1]["name"]]
    assert [item.index for item in result.rejected] == [1]
    assert {error.field for error in result.rejected[0].errors} == {"spec"}


@pytest.mark.parametrize("failure_stage", ["lookup", "persistence", "projection"])
def test_failed_batches_restore_all_canonical_changes(store, monkeypatch, failure_stage):
    originals = [
        store.record(
            type="fact",
            name=name,
            abstract=f"Orchid original {name}",
            fields={"project": "shop"},
            provenance=[f"Original evidence for {name}"],
        )
        for name in ("edited", "predecessor", "last-predecessor")
    ]
    before = {path: path.read_bytes() for path in store.layout.truth_files()}
    memory_path = store.root / "MEMORY.md"
    memory_before = memory_path.read_bytes()
    archive_before = {path for path in store.layout.archive.rglob("*") if path.is_file()}
    specs = [
        {
            "type": "fact",
            "name": "created",
            "abstract": "Orchid newly created",
            "provenance": ["Evidence retained even when the batch aborts"],
        },
        {
            "type": "fact",
            "name": "edited",
            "abstract": "Orchid first edit",
            "fields": {"project": "shop"},
        },
        {
            "type": "fact",
            "name": "edited",
            "abstract": "Orchid second edit",
            "fields": {"project": "shop"},
        },
        {
            "type": "fact",
            "name": "edited",
            "abstract": "Orchid moved",
            "fields": {"project": "billing"},
        },
        {
            "type": "fact",
            "name": "successor",
            "abstract": "Orchid successor",
            "supersedes": "predecessor",
        },
    ]
    if failure_stage == "lookup":
        specs.append(
            {
                "type": "fact",
                "name": "failed",
                "abstract": "Orchid rejected successor",
                "supersedes": "missing",
            }
        )
        error_type, message = NotFoundError, "no memory named missing"
    elif failure_stage == "persistence":
        specs.append(
            {
                "type": "fact",
                "name": "failed",
                "abstract": "Orchid incomplete successor",
                "supersedes": "last-predecessor",
            }
        )
        replace = store._replace_file
        failed = False

        def fail_predecessor_once(path, payload):
            nonlocal failed
            if path == originals[-1].path and not failed:
                failed = True
                raise OSError("injected write failure")
            replace(path, payload)

        monkeypatch.setattr(store, "_replace_file", fail_predecessor_once)
        error_type, message = OSError, "injected write failure"
    else:
        project = store._project
        failed = False

        def fail_after_projection_once():
            nonlocal failed
            report = project()
            if not failed:
                failed = True
                raise RuntimeError("injected projection failure")
            return report

        monkeypatch.setattr(store, "_project", fail_after_projection_once)
        error_type, message = RuntimeError, "injected projection failure"

    with pytest.raises(error_type, match=message):
        store.record_many(specs)

    assert {path: path.read_bytes() for path in store.layout.truth_files()} == before
    assert memory_path.read_bytes() == memory_before
    assert {hit.name for hit in Recall(store).recall("orchid")} == {
        record.name for record in originals
    }
    assert all(store.find(record.name).is_active() for record in originals)
    archive_after = {path for path in store.layout.archive.rglob("*") if path.is_file()}
    assert archive_before < archive_after
    store.rebuild_index()
    assert memory_path.read_bytes() == memory_before
    assert {hit.name for hit in Recall(store).recall("orchid")} == {
        record.name for record in originals
    }
