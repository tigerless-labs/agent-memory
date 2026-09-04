"""Writes that failed twice wait here for the next boundary instead of being lost.

Runtime state, not truth: losing it costs one retry, never a memory, because the messages
the write came from are still in the archive.
"""

from __future__ import annotations

import json

from .paths import StoreLayout
from .sessions import Pointer, parse_pointer, render_pointer

PENDING_SUFFIX = ".jsonl"
REDISTILL_DIRNAME = "redistill"


class Pending:
    def __init__(self, layout: StoreLayout):
        self._layout = layout

    def append(self, session: str, specs: list[dict[str, object]]) -> int:
        if not specs:
            return 0
        folder = self._layout.pending
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / f"{session}{PENDING_SUFFIX}").open("a", encoding="utf-8") as handle:
            for spec in specs:
                handle.write(json.dumps(spec, ensure_ascii=False) + "\n")
        return len(specs)

    def drain(self, session: str) -> list[dict[str, object]]:
        path = self._layout.pending / f"{session}{PENDING_SUFFIX}"
        if not path.exists():
            return []
        specs: list[dict[str, object]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                specs.append(payload)
        path.unlink()
        return specs

    def request_redistill(self, pointer: Pointer) -> bool:
        """Raw material that keeps being hit without any memory citing it goes back to the still."""
        folder = self._layout.pending / REDISTILL_DIRNAME
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{pointer.session}{PENDING_SUFFIX}"
        line = render_pointer(pointer)
        existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        if line in existing:
            return False
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        return True

    def redistill(self, session: str) -> list[Pointer]:
        path = self._layout.pending / REDISTILL_DIRNAME / f"{session}{PENDING_SUFFIX}"
        if not path.exists():
            return []
        found = [parse_pointer(line) for line in path.read_text(encoding="utf-8").splitlines()]
        return [pointer for pointer in found if pointer is not None]

    def clear_redistill(self, session: str) -> None:
        path = self._layout.pending / REDISTILL_DIRNAME / f"{session}{PENDING_SUFFIX}"
        path.unlink(missing_ok=True)

    def redistill_sessions(self) -> list[str]:
        folder = self._layout.pending / REDISTILL_DIRNAME
        if not folder.is_dir():
            return []
        return sorted(path.stem for path in folder.glob("*" + PENDING_SUFFIX))

    def sessions(self) -> list[str]:
        folder = self._layout.pending
        if not folder.is_dir():
            return []
        return sorted(path.stem for path in folder.glob("*" + PENDING_SUFFIX))
