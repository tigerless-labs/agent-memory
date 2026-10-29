"""Capture at a boundary: archive the increment and mark it consumed. Distilling is not here."""

from __future__ import annotations

import dataclasses

from agent_memory.core import prompts, sessions
from agent_memory.core.locking import file_lock
from agent_memory.core.store import Store
from agent_memory.core.watermark import Watermark

from .redaction import redact_all

SEGMENT_SEPARATOR = "\n\n"
RECORD_HINT = (
    "mem record --type <type> --field <key>=<value> "
    "--abstract <one line> --body <markdown> --provenance <message range>"
)
RECALL_HINT = "mem recall <query>"


@dataclasses.dataclass(frozen=True)
class Capture:
    session: str
    increment: tuple[str, ...]
    instruction: str
    archived: str
    pointer: str = ""

    def is_empty(self) -> bool:
        return not self.increment


def capture(store: Store, session: str, items: list[str], source: str = "") -> Capture:
    # Credentials are redacted before anything is persisted. The archive is the
    # input to distillation, so a key left in cleartext here would be read back
    # by the distiller and written into a long-lived memory entry.
    items = redact_all(items)
    with file_lock(store.layout.capture_lock, timeout=store.config.storage.lock_timeout_seconds):
        watermark = Watermark(store.layout, store.clock)
        increment = watermark.increment(session, items)
        if not increment:
            return Capture(session=session, increment=(), instruction="", archived="")
        appended = store.archive.append_session(session, list(increment))
        watermark.advance(session, len(items), source)
    return Capture(
        session=session,
        increment=tuple(increment),
        instruction=prompts.distill(SEGMENT_SEPARATOR.join(increment), RECORD_HINT),
        archived=str(sessions.session_path(store.layout, session)) if appended else "",
        pointer=sessions.render_pointer(appended) if appended else "",
    )
