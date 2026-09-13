"""Write races — correct and delete running against concurrent corrects lose nothing."""

import multiprocessing as mp

from agent_memory.core.store import Store

SHARED = "contested-fact"
CORRECTORS = ("corrector-alpha", "corrector-beta", "corrector-gamma", "corrector-delta")
CORRECT_ROUNDS = 12


def _correct(root: str, agent: str, started) -> None:
    store = Store(root, agent=agent)
    started.wait()
    for step in range(CORRECT_ROUNDS):
        store.correct(SHARED, provenance=[f"{agent} corrected the shared fact in round {step}"])


def _delete(root: str, started) -> None:
    store = Store(root, agent="deleter")
    started.wait()
    store.delete(SHARED)


def test_concurrent_corrects_keep_every_provenance(tmp_path):
    root = tmp_path / "store"
    store = Store(root)
    store.init()
    store.record(abstract="A shared fact that every writer corrects", type="fact", name=SHARED)
    context = mp.get_context("spawn")
    started = context.Event()
    workers = [
        context.Process(target=_correct, args=(str(root), name, started)) for name in CORRECTORS
    ]
    for worker in workers:
        worker.start()
    started.set()
    for worker in workers:
        worker.join()
    assert [worker.exitcode for worker in workers] == [0] * len(CORRECTORS)

    Store(root).sync_index()
    final = Store(root).find(SHARED)
    assert final is not None
    expected = {
        f"{name} corrected the shared fact in round {step}"
        for name in CORRECTORS
        for step in range(CORRECT_ROUNDS)
    }
    recorded = [(root / entry).read_text(encoding="utf-8") for entry in final.provenance]
    found = {excerpt for excerpt in expected for text in recorded if excerpt in text}
    assert found == expected
    assert len(final.provenance) == len(expected)


def test_delete_racing_corrects_never_ends_active(tmp_path):
    root = tmp_path / "store"
    store = Store(root)
    store.init()
    store.record(abstract="A shared fact that one writer deletes", type="fact", name=SHARED)
    context = mp.get_context("spawn")
    started = context.Event()
    deleter = context.Process(target=_delete, args=(str(root), started))
    workers = [deleter]
    workers += [
        context.Process(target=_correct, args=(str(root), name, started)) for name in CORRECTORS
    ]
    for worker in workers:
        worker.start()
    started.set()
    for worker in workers:
        worker.join()
    assert [worker.exitcode for worker in workers] == [0] * len(workers)

    Store(root).sync_index()
    final = Store(root).find(SHARED)
    assert final is not None
    assert not final.is_active()
    assert final.invalid_at
