"""Content-hash bookkeeping: what the index already knows, so a write reindexes only itself."""

from __future__ import annotations

import dataclasses
import hashlib
import pathlib
import sqlite3


@dataclasses.dataclass(frozen=True)
class ManifestDelta:
    added: tuple[str, ...]
    changed: tuple[str, ...]
    removed: tuple[str, ...]

    @property
    def touched(self) -> tuple[str, ...]:
        return self.added + self.changed

    def is_empty(self) -> bool:
        return not (self.added or self.changed or self.removed)


def content_hash(text: str, prefix_length: int) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:prefix_length]


class Manifest:
    def __init__(self, connection: sqlite3.Connection, prefix_length: int):
        self._connection = connection
        self._prefix_length = prefix_length

    def known(self) -> dict[str, str]:
        rows = self._connection.execute("SELECT path, content_hash FROM files").fetchall()
        return {row["path"]: row["content_hash"] for row in rows}

    def diff(self, present: dict[str, str]) -> ManifestDelta:
        known = self.known()
        added = tuple(sorted(path for path in present if path not in known))
        changed = tuple(
            sorted(
                path
                for path, digest in present.items()
                if path in known and known[path] != digest
            )
        )
        removed = tuple(sorted(path for path in known if path not in present))
        return ManifestDelta(added=added, changed=changed, removed=removed)

    def record(self, path: str, name: str, digest: str, at: str) -> None:
        self._connection.execute(
            "INSERT INTO files(path, name, content_hash, indexed_at) VALUES(?, ?, ?, ?) "
            "ON CONFLICT(path) DO UPDATE SET name=excluded.name, "
            "content_hash=excluded.content_hash, indexed_at=excluded.indexed_at",
            (path, name, digest, at),
        )

    def forget(self, path: str) -> None:
        self._connection.execute("DELETE FROM files WHERE path = ?", (path,))

    def hash_file(self, path: pathlib.Path) -> str:
        return content_hash(path.read_text(encoding="utf-8"), self._prefix_length)
