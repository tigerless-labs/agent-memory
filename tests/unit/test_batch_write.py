"""One turn, many memories.

A host pays a turn per tool call, so a per-record write API taxes exactly the hosts with the
tightest turn budgets — measured at 13x spread in capture across three hosts on identical
instructions. Batching removes the tax without changing what a memory is.
"""

import pytest
from agent_memory.core.errors import ValidationError
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
            (record.name, record.abstract, record.type, record.body)
            for record in store.records()
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
    result = store.record_many(
        [{"abstract": "wrong type", "type": "nonsense"}]
    )
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
    store.record(abstract="Worn twice as of 2023-04-01", type="fact",
                 name="converse-count-april")
    result = store.record_many([
        {
            "abstract": "Worn six times as of 2023-05-20",
            "type": "fact",
            "name": "converse-count-may",
            "supersedes": "converse-count-april",
        }
    ])
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


def test_an_empty_batch_is_not_an_error(store):
    result = store.record_many([])
    assert result.written == []
    assert result.rejected == []


def test_a_batch_rejects_a_malformed_spec_rather_than_guessing(store):
    with pytest.raises(ValidationError):
        store.record_many([{"not_a_field": 1}])
