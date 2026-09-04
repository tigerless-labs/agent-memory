"""The distillation watermark.

Correctness does not depend on any trigger firing. Every trigger means the same thing —
advance the mark — so a missed hook costs latency, never knowledge.
"""

from __future__ import annotations

import dataclasses
import json
import pathlib

from .clock import Clock
from .paths import StoreLayout

MARK_SUFFIX = ".json"
KEY_CONSUMED = "consumed"
KEY_DISTILLED = "distilled"
KEY_UPDATED_AT = "updated_at"
KEY_SOURCE = "source"


@dataclasses.dataclass(frozen=True)
class Mark:
    session: str
    consumed: int
    updated_at: str
    source: str
    distilled: int = 0

    def backlog(self) -> int:
        return max(0, self.consumed - self.distilled)


class Watermark:
    def __init__(self, layout: StoreLayout, clock: Clock | None = None):
        self._layout = layout
        self._clock = clock or Clock()

    def read(self, session: str) -> Mark:
        path = self._path(session)
        if not path.exists():
            return Mark(session=session, consumed=0, updated_at="", source="")
        payload = json.loads(path.read_text(encoding="utf-8"))
        return Mark(
            session=session,
            consumed=int(payload.get(KEY_CONSUMED, 0)),
            updated_at=str(payload.get(KEY_UPDATED_AT, "")),
            source=str(payload.get(KEY_SOURCE, "")),
            distilled=int(payload.get(KEY_DISTILLED, 0)),
        )

    def increment(self, session: str, items: list[str]) -> list[str]:
        return items[self.read(session).consumed :]

    def advance(self, session: str, consumed: int, source: str = "") -> Mark:
        current = self.read(session)
        return self._write(
            dataclasses.replace(
                current,
                consumed=max(current.consumed, consumed),
                updated_at=self._clock.now().isoformat(),
                source=source or current.source,
            )
        )

    def settle(self, session: str, distilled: int) -> Mark:
        """Distillation caught up to a message index; the archive mark stays where it is."""
        current = self.read(session)
        return self._write(
            dataclasses.replace(current, distilled=max(current.distilled, distilled))
        )

    def _write(self, mark: Mark) -> Mark:
        session = mark.session
        path = self._path(session)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    KEY_CONSUMED: mark.consumed,
                    KEY_UPDATED_AT: mark.updated_at,
                    KEY_SOURCE: mark.source,
                    KEY_DISTILLED: mark.distilled,
                }
            ),
            encoding="utf-8",
        )
        return mark

    def sessions(self) -> list[str]:
        if not self._layout.watermarks.exists():
            return []
        return sorted(path.stem for path in self._layout.watermarks.glob("*" + MARK_SUFFIX))

    def _path(self, session: str) -> pathlib.Path:
        return self._layout.watermarks / (session + MARK_SUFFIX)
