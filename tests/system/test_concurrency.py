"""M2 — two writers, one store. flock serializes them; neither write is lost."""

import multiprocessing as mp

from agent_memory.core.ledger import Decision, DecisionLedger
from agent_memory.core.store import Store

DECISIONS_PER_WRITER = 6


def _write(root: str, name: str) -> None:
    store = Store(root, agent=name)
    store.record(
        abstract=f"Concurrent write from {name} about the shared memory store",
        type="fact",
        name=name,
    )


def test_two_processes_recording_at_once_lose_nothing(tmp_path):
    root = tmp_path / "store"
    Store(root).init()
    context = mp.get_context("spawn")
    workers = [
        context.Process(target=_write, args=(str(root), name))
        for name in ("writer-alpha", "writer-beta")
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    assert [worker.exitcode for worker in workers] == [0, 0]

    store = Store(root)
    store.sync_index()
    names = {record.name for record in store.records()}
    assert {"writer-alpha", "writer-beta"} <= names
    index_lines = store.layout.memory_index.read_text(encoding="utf-8")
    assert "writer-alpha" in index_lines and "writer-beta" in index_lines


def _append(root: str, name: str) -> None:
    ledger = DecisionLedger(Store(root).layout)
    for step in range(DECISIONS_PER_WRITER):
        ledger.append(
            Decision(proposal_id=f"{name}-{step}", verdict="rejected", at="2026-01-01T00:00:00Z")
        )


def test_two_processes_appending_decisions_lose_nothing(tmp_path):
    root = tmp_path / "store"
    Store(root).init()
    context = mp.get_context("spawn")
    writers = ("writer-alpha", "writer-beta", "writer-gamma")
    workers = [
        context.Process(target=_append, args=(str(root), name))
        for name in writers
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    assert [worker.exitcode for worker in workers] == [0, 0, 0]

    decided = DecisionLedger(Store(root).layout).decided()
    expected = {f"{name}-{step}" for name in writers for step in range(DECISIONS_PER_WRITER)}
    assert expected <= set(decided)
