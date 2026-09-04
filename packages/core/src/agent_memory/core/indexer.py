"""Truth → projection. Incremental by content hash; a full rebuild is the same code path."""

from __future__ import annotations

import dataclasses
import pathlib

from . import chunking
from . import record as record_module
from .archive import SESSION_SUFFIX
from .clock import Clock
from .database import Database
from .embeddings import Embedder
from .errors import ValidationError
from .manifest import Manifest, content_hash
from .paths import StoreLayout
from .raw_index import RawIndex, source_name
from .record import MemoryRecord
from .search_index import SearchIndex
from .vector_index import VectorIndex


@dataclasses.dataclass(frozen=True)
class IndexReport:
    reindexed: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    unreadable: tuple[str, ...] = ()
    dangling_links: tuple[tuple[str, str], ...] = ()

    def is_empty(self) -> bool:
        return not (self.reindexed or self.removed)


class Indexer:
    def __init__(
        self, layout: StoreLayout, clock: Clock | None = None, embedder: Embedder | None = None
    ):
        self._layout = layout
        self._config = layout.config
        self._clock = clock or Clock()
        self._database = Database(layout)
        self._embedder = embedder

    def sync(self) -> IndexReport:
        present = self._present_hashes()
        with self._database.connect() as connection:
            manifest = Manifest(connection, self._config.index.hash_prefix_length)
            index = SearchIndex(connection)
            raw = RawIndex(connection)
            delta = manifest.diff(present)
            unreadable: list[str] = []
            reindexed: list[str] = []
            for relative in delta.touched:
                path = self._layout.root / relative
                if self._is_raw(path):
                    raw.upsert(
                        relative,
                        source_name(path),
                        path.read_text(encoding="utf-8"),
                        self._config.index.raw_chunk_chars,
                    )
                    manifest.record(
                        relative, source_name(path), present[relative],
                        self._clock.now().isoformat(),
                    )
                    reindexed.append(relative)
                    continue
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
                raw.remove(relative)
                manifest.forget(relative)
            if self._config.index.vector_enabled:
                assert self._embedder is not None
                self._sync_vectors(connection, present, self._embedder)
            dangling = self._dangling_links(index)
        return IndexReport(
            reindexed=tuple(reindexed),
            removed=delta.removed,
            unreadable=tuple(unreadable),
            dangling_links=dangling,
        )

    def _sync_vectors(
        self, connection, present: dict[str, str], embedder: Embedder
    ) -> None:
        vectors = VectorIndex(connection, embedder, self._config.index.vector_model)
        memory_paths = {
            relative: digest
            for relative, digest in present.items()
            if not self._is_raw(self._layout.root / relative)
        }
        known = vectors.known()
        for relative in sorted(set(known) - set(memory_paths)):
            vectors.remove_path(relative)
        for relative, digest in sorted(memory_paths.items()):
            if known.get(relative) == (digest, self._config.index.vector_model):
                continue
            record = self._load(self._layout.root / relative)
            if record is not None:
                vectors.upsert(
                    relative, digest, record, chunking.chunks(record, self._config)
                )

    def rebuild(self) -> IndexReport:
        self._database.drop()
        return self.sync()

    def _is_raw(self, path: pathlib.Path) -> bool:
        return path.parent == self._layout.sessions

    def _present_hashes(self) -> dict[str, str]:
        present: dict[str, str] = {}
        for path in self._layout.truth_files() + self._layout.archived_files() + self._raw_files():
            relative = str(path.relative_to(self._layout.root))
            present[relative] = content_hash(
                path.read_text(encoding="utf-8"), self._config.index.hash_prefix_length
            )
        return present

    def _raw_files(self) -> list[pathlib.Path]:
        if not self._layout.config.write.session_archive_enabled:
            return []
        return sorted(self._layout.sessions.glob("*" + SESSION_SUFFIX))

    def _load(self, path: pathlib.Path) -> MemoryRecord | None:
        domain = self._layout.domain_of(path)
        if domain is None:
            return None
        record = MemoryRecord.from_text(path.read_text(encoding="utf-8"), domain, path)
        try:
            record_module.validate(record, self._config)
        except ValidationError:
            return None
        return record

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
