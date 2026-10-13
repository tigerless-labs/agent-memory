"""The hook timeout watchdog arms itimer signals where they exist and degrades
to a no-op where they do not, so the hook entry imports and runs on Windows."""

import signal

import pytest
from agent_memory.adapters import hook_entry


def test_arm_disarm_are_noop_without_itimer(monkeypatch):
    monkeypatch.delattr(signal, "setitimer", raising=False)
    monkeypatch.delattr(signal, "SIGALRM", raising=False)
    hook_entry._arm(5.0)
    hook_entry._disarm()


def test_arm_disarm_round_trip_with_itimer():
    if not hasattr(signal, "setitimer") or not hasattr(signal, "SIGALRM"):
        pytest.skip("itimer signals unavailable on this platform")
    hook_entry._arm(5.0)
    hook_entry._disarm()
