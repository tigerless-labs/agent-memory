"""The injection track: a byte-prefix of the root index rendered from current truth.

Deterministic floor of the three read tracks — it costs no tool call and cannot miss."""

from __future__ import annotations

from . import memory_md
from .store import Store

NEWLINE = b"\n"


def payload(store: Store) -> str:
    if not store.config.recall.injection_enabled:
        return ""
    if not store.layout.memory_index.exists():
        return ""
    data = memory_md.render(store.records(), store.config, str(store.root)).encode("utf-8")
    budget = store.config.recall.injection_budget_bytes
    if len(data) <= budget:
        return data.decode("utf-8")
    cut = data.rfind(NEWLINE, 0, budget)
    return data[: cut if cut > 0 else budget].decode("utf-8", errors="ignore")
