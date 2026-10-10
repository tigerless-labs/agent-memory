"""The duplicate keeper must be revalidated inside the T0 invalidation lock.

docs/TODO.md (management follow-ups): the stale-write detection guards only
the record being invalidated, so a keeper that dies between Manage's snapshot
and the merge would orphan the duplicate into a dead name. These tests pin
the revalidation contract of ``Store.merge_exact_duplicate`` and the race it
closes."""

import multiprocessing
import sys

import pytest

from agent_memory.core.manage import ACTION_DUPLICATE_MERGED, Manage
from agent_memory.core.store import Store


def _duplicate_pair(store: Store):
    first = store.record(type="fact", name="dup-a", abstract="Same", body="Same body")
    # Explicit fields keep the derived subject identical, which is what makes
    # the pair an exact duplicate despite the different file names.
    second = store.record(
        type="fact",
        name="dup-b",
        abstract="Same",
        body="Same body",
        fields=first.fields,
    )
    return first, second


def test_merge_exact_duplicate_skips_a_superseded_keeper(store):
    first, second = _duplicate_pair(store)
    store.supersede("dup-a", "dup-b")

    merged = store.merge_exact_duplicate(second, first, store.clock.timestamp())

    assert merged is None
    assert store.find("dup-b").is_active(), "duplicate was orphaned into a dead keeper"


def test_merge_exact_duplicate_skips_a_deleted_keeper(store):
    first, second = _duplicate_pair(store)
    store.delete("dup-a")

    merged = store.merge_exact_duplicate(second, first, store.clock.timestamp())

    assert merged is None
    assert store.find("dup-b").is_active(), "duplicate was orphaned into a dead keeper"


def test_merge_exact_duplicate_merges_into_a_live_keeper(store):
    first, second = _duplicate_pair(store)

    merged = store.merge_exact_duplicate(second, first, store.clock.timestamp())

    assert merged is not None
    duplicate = store.find("dup-b")
    assert not duplicate.is_active()
    assert duplicate.superseded_by == "dup-a"
    assert store.find("dup-a").is_active()


def test_manage_does_not_merge_into_a_keeper_that_died_after_the_snapshot(store):
    """The race, single-process: hand _merge_exact_duplicates a snapshot in
    which both duplicates were active, then let the keeper die before the
    store call. On the old invalidate-plus-rewrite path this orphaned the
    duplicate into the dead keeper; with the revalidating merge it must back
    off."""
    first, second = _duplicate_pair(store)
    snapshot = [first, second]  # both active when Manage took this snapshot
    store.supersede("dup-a", "dup-b")  # the keeper dies after the snapshot

    actions = Manage(store)._merge_exact_duplicates(snapshot)

    assert actions == [], "a merge into a dead keeper was recorded"
    assert store.find("dup-b").is_active(), "duplicate was orphaned into a dead keeper"


def _snapshot_pause_merge(root, snapshot_taken, release_merge):
    store = Store(root)
    records = store.records()
    first = next(record for record in records if record.name == "dup-a")
    second = next(record for record in records if record.name == "dup-b")
    snapshot_taken.set()
    if not release_merge.wait(8):
        raise TimeoutError("merge was never released")
    store.merge_exact_duplicate(second, first, store.clock.timestamp())


@pytest.mark.skipif(sys.platform == "win32", reason="fork context is POSIX-only")
def test_keeper_death_between_snapshot_and_merge_does_not_orphan(store):
    """The race from the TODO, driven for real: one process holds the pair
    from a snapshot and pauses before merging; the keeper is superseded in
    the meantime; the merge must back off, not invalidate into the dead name."""
    _duplicate_pair(store)
    context = multiprocessing.get_context("fork")
    snapshot_taken = context.Event()
    release_merge = context.Event()
    child = context.Process(
        target=_snapshot_pause_merge, args=(store.root, snapshot_taken, release_merge)
    )
    child.start()
    try:
        assert snapshot_taken.wait(5), "child never reached its snapshot boundary"
        store.supersede("dup-a", "dup-b")
    finally:
        release_merge.set()
        child.join(10)
        if child.is_alive():
            child.terminate()
            child.join(5)
    assert child.exitcode == 0, "child failed or deadlocked"
    assert store.find("dup-b").is_active(), "duplicate was orphaned into a dead keeper"
