"""A write must be able to say what it replaces, in one call.

Superseding used to cost three: recall the old name, record the new entry, then correct the
old one to point at it. Across 3,744 memories written in a 120-episode benchmark run, the
supersede edge count was zero — the mechanism the whole time-travel guarantee rests on was
reachable in principle and unused in practice.
"""

import pytest
from agent_memory.core.errors import NotFoundError, ValidationError
from agent_memory.core.recall import Recall


def test_a_new_record_can_supersede_an_existing_one_in_a_single_write(store):
    store.record(
        abstract="Worn the new sneakers 4 times as of 2023-05-30",
        type="fact", name="sneaker-wear-count-may",
    )
    store.record(
        abstract="Worn the new sneakers 6 times as of 2023-06-20",
        type="fact", name="sneaker-wear-count-june",
        supersedes="sneaker-wear-count-may",
    )

    superseded = store.find("sneaker-wear-count-may")
    assert superseded.superseded_by == "sneaker-wear-count-june"
    assert superseded.path.exists()

    names = [hit.name for hit in Recall(store).recall("sneakers worn times count")]
    assert "sneaker-wear-count-june" in names
    assert "sneaker-wear-count-may" not in names


def test_the_superseded_value_is_still_reachable_by_time_travel(store):
    store.record(
        abstract="Worn the new sneakers 4 times as of 2023-05-30",
        type="fact", name="sneaker-wear-count-may",
        valid_from="2023-05-30",
    )
    store.record(
        abstract="Worn the new sneakers 6 times as of 2023-06-20",
        type="fact", name="sneaker-wear-count-june",
        valid_from="2023-06-20",
        supersedes="sneaker-wear-count-may",
    )
    earlier = [hit.name for hit in Recall(store).recall("sneakers worn", as_of="2023-06-01")]
    assert "sneaker-wear-count-may" in earlier
    assert "sneaker-wear-count-june" not in earlier


def test_superseding_something_that_does_not_exist_is_rejected(store):
    with pytest.raises(NotFoundError):
        store.record(
            abstract="Replaces a memory nobody wrote",
            type="fact", name="orphan-successor",
            supersedes="never-written",
        )


def test_a_record_cannot_supersede_itself(store):
    store.record(abstract="A standing fact", type="fact", name="standing-fact")
    with pytest.raises(ValidationError):
        store.record(
            abstract="A standing fact, restated",
            type="fact", name="standing-fact",
            supersedes="standing-fact",
        )


def test_supersede_on_write_goes_through_the_same_pipeline_as_any_other_write(store):
    store.record(abstract="The older value", type="fact", name="older")
    store.record(
        abstract="The newer value", type="fact", name="newer", supersedes="older"
    )
    report = store.sync_index()
    assert report.reindexed == ()
    assert report.dangling_links == ()
