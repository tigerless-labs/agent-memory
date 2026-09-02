"""The read surface that decides disclosure itself.

`recall` hands back an L0 list and leaves the ladder to the caller: search again, or open an
entry, or stop. That delegation is the design's intent for an agent that knows what it is
looking for, and it is measurably expensive for one that does not — an agent driving its own
retrieval swings the same store's answers by seven per hundred between identical replays, and
scores well below the same store read on a fixed policy (P5/fixed, docs in experiments/).

So the ladder is also available as one call: the store runs the recall, opens the top entries
to full text, and returns a context block ready to be reasoned over. Same retrieval, same
scoring, same eligibility — the only thing that moves inside is who decides when to stop.
"""

from __future__ import annotations

import dataclasses

from .recall import Recall
from .store import LEVEL_FULL, Store

HEADER = "Entries from your memory store, most relevant first:"
NOTHING_FOUND = "Your memory store returned nothing for this question."
ENTRY_SEPARATOR = "\n\n"
BULLET = "- "


@dataclasses.dataclass(frozen=True)
class Context:
    text: str
    entries: int
    names: tuple[str, ...]

    def is_empty(self) -> bool:
        return self.entries == 0


def build(
    store: Store,
    query: str,
    scope: str | None = None,
    as_of: str | None = None,
    deep: bool = False,
    limit: int | None = None,
) -> Context:
    hits = Recall(store).recall(query, scope=scope, as_of=as_of, deep=deep, limit=limit)
    if not hits:
        return Context(text=NOTHING_FOUND, entries=0, names=())

    full_text_entries = store.config.recall.context_full_text_entries
    rendered = [
        _entry(hit, _body(store, hit.name) if position < full_text_entries else "")
        for position, hit in enumerate(hits)
    ]
    return Context(
        text=HEADER + ENTRY_SEPARATOR + ENTRY_SEPARATOR.join(rendered),
        entries=len(hits),
        names=tuple(hit.name for hit in hits),
    )


def _entry(hit, body: str) -> str:
    head = BULLET + hit.abstract
    return f"{head}\n{body}" if body.strip() else head


def _body(store: Store, name: str) -> str:
    try:
        return store.read(name, level=LEVEL_FULL).text
    except Exception:
        return ""
