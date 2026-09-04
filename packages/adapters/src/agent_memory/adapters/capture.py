"""Capture at a boundary: archive the increment, hand it to the host, advance only on commit."""

from __future__ import annotations

import dataclasses

from agent_memory.core import prompts
from agent_memory.core.store import Store
from agent_memory.core.watermark import Watermark

SEGMENT_SEPARATOR = "\n\n"
RECORD_HINT = (
    "mem record --type <type> --field <key>=<value> "
    "--abstract <one line> --body <markdown> --provenance <verbatim excerpt>"
)
RECALL_HINT = "mem recall <query>"


@dataclasses.dataclass(frozen=True)
class Capture:
    session: str
    increment: tuple[str, ...]
    instruction: str
    archived: str

    def is_empty(self) -> bool:
        return not self.increment


def capture(store: Store, session: str, items: list[str], source: str = "") -> Capture:
    watermark = Watermark(store.layout, store.clock)
    increment = watermark.increment(session, items)
    if not increment:
        return Capture(session=session, increment=(), instruction="", archived="")
    segment = SEGMENT_SEPARATOR.join(increment)
    archived = store.archive.append_session(session, segment)
    return Capture(
        session=session,
        increment=tuple(increment),
        instruction=prompts.distill(segment, RECORD_HINT),
        archived=str(archived) if archived else "",
    )


def commit(store: Store, session: str, consumed: int, source: str = "") -> int:
    return Watermark(store.layout, store.clock).advance(session, consumed, source).consumed
