"""The injection track: a byte-prefix of MEMORY.md, never a summary of it.

Deterministic floor of the three read tracks — it costs no tool call and cannot miss."""

from __future__ import annotations

from .store import Store

NEWLINE = b"\n"


def payload(store: Store) -> str:
    if not store.config.recall.injection_enabled:
        return ""
    if not store.layout.memory_index.exists():
        return ""
    data = store.layout.memory_index.read_bytes()
    budget = store.config.recall.injection_budget_bytes
    if len(data) <= budget:
        return data.decode("utf-8")
    cut = data.rfind(NEWLINE, 0, budget)
    return data[: cut if cut > 0 else budget].decode("utf-8", errors="ignore")
