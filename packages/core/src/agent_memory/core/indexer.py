"""Truth → projection. Incremental by content hash; a full rebuild is the same code path."""

from __future__ import annotations

import dataclasses
import pathlib

from . import chunking
from .clock import Clock
from .database import Database
from .manifest import Manifest, content_hash
from .paths import StoreLayout
from .record import MemoryRecord
from .search_index import SearchIndex


@dataclasses.dataclass(frozen=True)
class IndexReport:
    reindexed: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    unreadable: tuple[str, ...] = ()
    dangling_links: tuple[tuple[str, str], ...] = ()

    def is_empty(self) -> bool:
        return not (self.reindexed or self.removed)


class Indexer:
    def __init__(self, layout: StoreLayout, clock: Clock | None = None):
        self._layout = layout
        self._config = layout.config
        self._clock = clock or Clock()
        self._database = Database(layout)

    def sync(self) -> IndexReport:
        present = self._present_hashes()
        with self._database.connect() as connection:
            manifest = Manifest(connection, self._config.index.hash_prefix_length)
            index = SearchIndex(connection)
            delta = manifest.diff(present)
            unreadable: list[str] = []
            reindexed: list[str] = []
            for relative in delta.touched:
                path = self._layout.root / relative
                record = self._load(path)
                if record is None:
                    unreadable.append(relative)
                    continue
                index.remove_path(relative)
                index.upsert(
                    record,
                    chunking.chunks(record, self._config),
                    self._layout.is_archived(path),
                    relative,
                )
                manifest.record(
                    relative, record.name, present[relative], self._clock.now().isoformat()
                )
                reindexed.append(relative)
            for relative in delta.removed:
                index.remove_path(relative)
                manifest.forget(relative)
            dangling = self._dangling_links(index)
        return IndexReport(
            reindexed=tuple(reindexed),
            removed=delta.removed,
            unreadable=tuple(unreadable),
            dangling_links=dangling,
        )

    def rebuild(self) -> IndexReport:
        self._database.drop()
        return self.sync()

    def _present_hashes(self) -> dict[str, str]:
        present: dict[str, str] = {}
        for path in self._layout.truth_files() + self._layout.archived_files():
            relative = str(path.relative_to(self._layout.root))
            present[relative] = content_hash(
                path.read_text(encoding="utf-8"), self._config.index.hash_prefix_length
            )
        return present

    def _load(self, path: pathlib.Path) -> MemoryRecord | None:
        domain = self._layout.domain_of(path)
        if domain is None:
            return None
        record = MemoryRecord.from_text(path.read_text(encoding="utf-8"), domain, path)
        return record if record.name else None

    def _dangling_links(self, index: SearchIndex) -> tuple[tuple[str, str], ...]:
        rows = index.rows()
        known = {row["name"] for row in rows}
        dangling: list[tuple[str, str]] = []
        for row in rows:
            for link in str(row["links"]).split(","):
                target = link.strip()
                if target and target not in known:
                    dangling.append((str(row["name"]), target))
        return tuple(sorted(dangling))
