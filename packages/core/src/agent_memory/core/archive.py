"""Raw material, append-only (Invariant 4). Nothing here removes anything."""

from __future__ import annotations

import hashlib
import pathlib

from .clock import Clock
from .paths import StoreLayout

PROVENANCE_SUFFIX = ".md"
SESSION_SUFFIX = ".txt"


class Archive:
    def __init__(self, layout: StoreLayout, clock: Clock | None = None):
        self._layout = layout
        self._clock = clock or Clock()

    def append_provenance(self, name: str, excerpt: str, source: str = "") -> pathlib.Path:
        folder = self._layout.provenance / name
        folder.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
        short = digest[: self._layout.config.index.hash_prefix_length]
        path = folder / f"{self._clock.stamp()}-{short}{PROVENANCE_SUFFIX}"
        header = f"# provenance: {name}\n\nrecorded_at: {self._clock.now().isoformat()}\n"
        origin = f"source: {source}\n" if source else ""
        path.write_text(header + origin + "\n" + excerpt.strip() + "\n", encoding="utf-8")
        return path

    def provenance_of(self, name: str) -> list[pathlib.Path]:
        folder = self._layout.provenance / name
        return sorted(folder.glob("*" + PROVENANCE_SUFFIX)) if folder.exists() else []

    def append_session(self, session_id: str, transcript: str) -> pathlib.Path | None:
        if not self._layout.config.write.session_archive_enabled:
            return None
        self._layout.sessions.mkdir(parents=True, exist_ok=True)
        path = self._layout.sessions / f"{session_id}{SESSION_SUFFIX}"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(transcript.rstrip() + "\n")
        return path
