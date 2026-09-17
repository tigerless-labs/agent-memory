import multiprocessing

from agent_memory.core.search_index import SearchIndex
from agent_memory.core.store import Store


def _correct_abstract(root, read_started, release_read):
    writer = Store(root)
    find = writer.find
    paused = False

    def find_and_pause(name):
        nonlocal paused
        record = find(name)
        if name == "source" and not paused:
            paused = True
            read_started.set()
            if not release_read.wait(8):
                raise TimeoutError("first writer was not released")
        return record

    writer.find = find_and_pause
    writer.correct("source", abstract="New abstract from A")


def _correct_body(root, started, read_started, finished):
    started.set()
    writer = Store(root)
    find = writer.find

    def find_and_signal(name):
        record = find(name)
        if name == "source":
            read_started.set()
        return record

    writer.find = find_and_signal
    writer.correct("source", body="newbodytoken from B")
    finished.set()


def test_independent_process_corrections_keep_both_updates_and_projection(store):
    store.record(type="fact", name="source", abstract="Old abstract", body="Old body")
    context = multiprocessing.get_context("fork")
    read_started = context.Event()
    release_read = context.Event()
    second_started = context.Event()
    second_read = context.Event()
    second_finished = context.Event()
    first = context.Process(target=_correct_abstract, args=(store.root, read_started, release_read))
    second = context.Process(
        target=_correct_body, args=(store.root, second_started, second_read, second_finished)
    )

    try:
        first.start()
        assert read_started.wait(5), "first writer did not reach its read boundary"
        second.start()
        assert second_started.wait(5), "second writer did not start"
        if second_read.wait(2):
            assert second_finished.wait(5), "second writer read but did not finish"
    finally:
        release_read.set()
        for process in (first, second):
            if process.pid is not None:
                process.join(10)
                if process.is_alive():
                    process.terminate()
                    process.join(5)

    assert first.exitcode == 0, "first correction failed or deadlocked"
    assert second.exitcode == 0, "second correction failed or deadlocked"
    canonical = store.find("source")
    assert canonical.abstract == "New abstract from A"
    assert canonical.body == "newbodytoken from B"
    with store._database.connect() as connection:
        index = SearchIndex(connection)
        assert index.row("source")["abstract"] == canonical.abstract
        assert any(item.name == "source" for item in index.match("newbodytoken", 10))
    store.rebuild_index()
    assert store.find("source").body == canonical.body
