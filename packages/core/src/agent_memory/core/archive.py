"""Raw material, append-only (Invariant 4). Nothing here removes anything."""

from __future__ import annotations

import hashlib
import pathlib

from . import sessions
from .clock import Clock
from .errors import FieldError, ValidationError
from .paths import StoreLayout
from .record import MemoryRecord

PROVENANCE_SUFFIX = ".md"
SESSION_SUFFIX = sessions.SESSION_SUFFIX


class Archive:
    def __init__(self, layout: StoreLayout, clock: Clock | None = None):
        self._layout = layout
        self._clock = clock or Clock()

    def archive_memory(self, record: MemoryRecord) -> pathlib.Path:
        if record.is_active() or record.path is None:
            raise ValidationError([FieldError("status", "only persisted invalid memories archive")])
        source = record.path
        if self._layout.type_of(source) != record.type:
            raise ValidationError([FieldError("path", "memory must belong to this store")])
        if self._layout.is_archived_memory(source):
            return source
        target = self._layout.archived_memories / source.relative_to(self._layout.root)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise FileExistsError(f"archive destination already exists: {target}")
        source.rename(target)
        record.path = target
        return target

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

    def append_session(
        self, session_id: str, items: str | list[str] | list[dict[str, object]]
    ) -> sessions.Pointer | None:
        if not self._layout.config.write.session_archive_enabled:
            return None
        if isinstance(items, str):
            items = [line for line in items.splitlines() if line.strip()]
        return sessions.append(self._layout, session_id, items, self._clock)
