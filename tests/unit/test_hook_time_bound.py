"""A stuck hook gives the host back control within its bound, on every platform."""

import io
import json
import time

from agent_memory.adapters import hook_entry


def _run_stuck_hook(store, monkeypatch, *, bound_seconds, stuck_seconds):
    store.config.write.hook_timeout_seconds = bound_seconds
    store.config.save(store.root)

    def stuck(_store, _event, *args, **kwargs):
        deadline = time.monotonic() + stuck_seconds
        while time.monotonic() < deadline:
            time.sleep(0.01)
        return {}

    monkeypatch.setattr(hook_entry, "handle", stuck)
    event = {"hook_event_name": "Stop", "session_id": "s", "store": str(store.root)}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(event)))
    started = time.monotonic()
    code = hook_entry.main([])
    return code, time.monotonic() - started


def test_a_stuck_hook_exits_cleanly_within_its_bound(store, monkeypatch):
    code, elapsed = _run_stuck_hook(store, monkeypatch, bound_seconds=0.3, stuck_seconds=10)

    assert code == hook_entry.EXIT_OK
    assert elapsed < 5
    log = (store.layout.state_dir / hook_entry.LOG_FILENAME).read_text(encoding="utf-8")
    assert "_Timeout" in log


def test_a_finished_hook_leaves_no_pending_interruption(store, monkeypatch):
    code, _ = _run_stuck_hook(store, monkeypatch, bound_seconds=0.3, stuck_seconds=0)

    assert code == hook_entry.EXIT_OK
    time.sleep(0.6)
    log_path = store.layout.state_dir / hook_entry.LOG_FILENAME
    assert not log_path.exists() or "_Timeout" not in log_path.read_text(encoding="utf-8")
