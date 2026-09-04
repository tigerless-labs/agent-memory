"""Writes that failed twice wait here for the next boundary instead of being lost.

Runtime state, not truth: losing it costs one retry, never a memory, because the messages
the write came from are still in the archive.
"""

from __future__ import annotations

import json

from .paths import StoreLayout

PENDING_SUFFIX = ".jsonl"


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

    def sessions(self) -> list[str]:
        folder = self._layout.pending
        if not folder.is_dir():
            return []
        return sorted(path.stem for path in folder.glob("*" + PENDING_SUFFIX))
