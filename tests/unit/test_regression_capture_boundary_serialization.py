import concurrent.futures
import threading

from agent_memory.adapters.capture import capture
from agent_memory.core import sessions
from agent_memory.core.watermark import Watermark


def test_overlapping_capture_boundaries_archive_each_increment_once(store, monkeypatch):
    original = Watermark.increment
    entered = threading.Event()
    release = threading.Event()
    second_started = threading.Event()
    second_increment = threading.Event()
    calls = []

    def delayed(self, session, items):
        result = original(self, session, items)
        calls.append(1)
        if len(calls) > 1:
            second_increment.set()
        if len(calls) == 1:
            entered.set()
            assert release.wait(5)
        return result

    monkeypatch.setattr(Watermark, "increment", delayed)

    def second():
        second_started.set()
        return capture(store, "parallel", ["user: Fixture"])

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(capture, store, "parallel", ["user: Fixture"])
        assert entered.wait(5)
        other = pool.submit(second)
        assert second_started.wait(5)
        second_increment.wait(0.5)
        release.set()
        results = [first.result(), other.result()]
    assert sum(not result.is_empty() for result in results) == 1
    assert len(sessions.read(store.layout, "parallel")) == 1
