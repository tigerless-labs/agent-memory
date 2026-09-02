"""Two ways to sit the exam.

The agentic exam lets the host drive its own retrieval, which is how the system is really
used — and which makes the host's search behaviour part of every measurement. Repeated
replays of one frozen configuration moved by +/-7 answers per 120 episodes, enough to bury
any difference between memory configurations.

The fixed exam removes that degree of freedom: the harness performs the recall itself, builds
one context from the result, and asks a single question with no tools. What varies is then one
generation instead of an agent loop, which is what makes memory configurations comparable.
"""

from __future__ import annotations

import dataclasses

from agent_memory.core.recall import Recall
from agent_memory.core.store import LEVEL_FULL, Store

MODE_AGENTIC = "agentic"
MODE_FIXED = "fixed"
MODES = (MODE_AGENTIC, MODE_FIXED)

ENTRY_SEPARATOR = "\n\n"
CONTEXT_HEADER = "Entries from your memory store, most relevant first:"
NOTHING_FOUND = "Your memory store returned nothing for this question."


@dataclasses.dataclass(frozen=True)
class FixedContext:
    text: str
    entries: int

    def is_empty(self) -> bool:
        return self.entries == 0


def build_context(store: Store, question: str, full_text_entries: int) -> FixedContext:
    """Deterministic: same store and same question always give the same context."""
    hits = Recall(store).recall(question, deep=store.config.recall.raw_enabled)
    if not hits:
        return FixedContext(text=NOTHING_FOUND, entries=0)
    rendered: list[str] = []
    for position, hit in enumerate(hits):
        body = ""
        if position < full_text_entries:
            body = _full_text(store, hit.name)
        rendered.append(_entry(hit, body))
    return FixedContext(
        text=CONTEXT_HEADER + ENTRY_SEPARATOR + ENTRY_SEPARATOR.join(rendered),
        entries=len(hits),
    )


def _entry(hit, body: str) -> str:
    head = f"- {hit.abstract}"
    return f"{head}\n{body}" if body.strip() else head


def _full_text(store: Store, name: str) -> str:
    try:
        return store.read(name, level=LEVEL_FULL).text
    except Exception:
        return ""
