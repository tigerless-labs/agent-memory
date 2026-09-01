"""M2 — two writers, one store. flock serializes them; neither write is lost."""

import multiprocessing as mp

from agent_memory.core.store import Store


def _write(root: str, name: str) -> None:
    store = Store(root, agent=name)
    store.record(
        abstract=f"Concurrent write from {name} about the shared memory store",
        type="fact",
        domain="project",
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
