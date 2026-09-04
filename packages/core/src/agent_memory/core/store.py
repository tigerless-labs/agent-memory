"""The single write path (Invariant 2). Every adapter, and Manage itself, enters here."""

from __future__ import annotations

import dataclasses
import pathlib

from . import chunking, memory_md
from . import record as record_module
from .access_log import KIND_READ, AccessEntry, AccessLog
from .archive import Archive
from .clock import Clock
from .config import Config, resolve_store_root
from .database import Database
from .embeddings import Embedder, create_embedder
from .errors import FieldError, NotFoundError, ValidationError
from .indexer import Indexer, IndexReport
from .locking import store_lock
from .paths import MEMORY_SUFFIX, StoreLayout
from .record import STATUS_RETIRED, MemoryRecord
from .search_index import SearchIndex
from .slug import slugify

LEVEL_ABSTRACT = "abstract"
LEVEL_OUTLINE = "outline"
LEVEL_FULL = "full"
LEVELS = (LEVEL_ABSTRACT, LEVEL_OUTLINE, LEVEL_FULL)
UNKNOWN_AGENT = "unknown"


RECORD_FIELDS = frozenset(
    {
        "abstract", "type", "domain", "body", "name", "author", "links",
        "topic", "valid_from", "provenance", "weight", "supersedes",
    }
)


@dataclasses.dataclass(frozen=True)
class Rejected:
    index: int
    errors: list[FieldError]

    def as_dict(self) -> dict[str, object]:
        return {"index": self.index, "errors": [error.as_dict() for error in self.errors]}


@dataclasses.dataclass(frozen=True)
class BatchResult:
    written: list[MemoryRecord]
    rejected: list[Rejected]

    def as_dict(self) -> dict[str, object]:
        return {
            "written": [
                {"name": record.name, "path": str(record.path), "updated": record.updated}
                for record in self.written
            ],
            "rejected": [item.as_dict() for item in self.rejected],
        }


@dataclasses.dataclass(frozen=True)
class ReadResult:
    record: MemoryRecord
    level: str
    text: str
    outline: tuple[str, ...]


class Store:
    def __init__(
        self,
        root: str | pathlib.Path | None = None,
        config: Config | None = None,
        clock: Clock | None = None,
        agent: str = UNKNOWN_AGENT,
        embedder: Embedder | None = None,
    ):
        self.root = resolve_store_root(root)
        self.config = config or Config.load(self.root)
        self.layout = StoreLayout(self.root, self.config)
        self.clock = clock or Clock()
        self.agent = agent
        self.archive = Archive(self.layout, self.clock)
        if self.config.index.vector_enabled and embedder is None:
            embedder = create_embedder(self.config.index.vector_model)
        self.embedder = embedder
        self._indexer = Indexer(self.layout, self.clock, embedder)
        self._database = Database(self.layout)

    def init(self) -> StoreLayout:
        self.layout.ensure()
        if not (self.root / "config.toml").exists():
            self.config.save(self.root)
        self._indexer.sync()
        return self.layout

    def record(self, **spec: object) -> MemoryRecord:
        """One memory. A batch of one, so there is exactly one way into the store."""
        result = self.record_many([spec])
        if result.rejected:
            raise ValidationError(result.rejected[0].errors)
        return result.written[0]

    def record_many(self, specs: list[dict[str, object]]) -> BatchResult:
        """Many memories, one lock and one projection.

        A host pays a turn per tool call, so writing one memory per call taxes exactly the
        hosts with the tightest turn budgets. Batching removes that tax and costs the store
        nothing: each record is prepared and persisted exactly as a single write would be,
        and only the projection is shared.
        """
        self.layout.ensure()
        written: list[MemoryRecord] = []
        rejected: list[Rejected] = []
        for spec in specs:
            unknown = set(spec) - RECORD_FIELDS
            if unknown:
                raise ValidationError(
                    [FieldError("spec", f"unknown field: {', '.join(sorted(unknown))}")]
                )
        if not specs:
            return BatchResult(written=written, rejected=rejected)
        with store_lock(self.layout):
            for index, spec in enumerate(specs):
                try:
                    written.append(self._write_one(spec))
                except ValidationError as error:
                    rejected.append(Rejected(index=index, errors=list(error.errors)))
            self._project()
        return BatchResult(written=written, rejected=rejected)

    def _write_one(self, spec: dict[str, object]) -> MemoryRecord:
        abstract = str(spec.get("abstract") or "")
        name = spec.get("name")
        topic = spec.get("topic")
        supersedes = spec.get("supersedes")
        provenance = _as_sequence(spec.get("provenance"))
        weight = spec.get("weight")

        slug = str(name) if name else slugify(abstract, self.config.storage.slug_max_length)
        now = self.clock.timestamp()
        existing = self.find(slug)
        candidate = MemoryRecord(
            name=slug,
            abstract=abstract.strip(),
            type=str(spec.get("type") or ""),
            author=str(spec.get("author") or self.agent),
            created=existing.created if existing else now,
            updated=now,
            body=str(spec.get("body") or ""),
            valid_from=str(spec.get("valid_from") or "")
            or (existing.valid_from if existing else now),
            weight=float(str(weight)) if weight is not None else self.config.weight.initial,
            links=[str(link) for link in _as_sequence(spec.get("links"))],
            provenance=list(existing.provenance) if existing else [],
            domain=str(spec.get("domain") or ""),
        )
        target = self._target_path(candidate, str(topic) if topic else None, existing)
        candidate.path = target
        record_module.validate(candidate, self.config)
        record_module.canonicalise_dates(candidate)
        self._reject_depth(target)
        predecessor = self._predecessor(candidate, str(supersedes) if supersedes else None)

        for excerpt in provenance:
            stored = self.archive.append_provenance(
                candidate.name, str(excerpt), source=self.agent
            )
            candidate.provenance.append(str(stored.relative_to(self.root)))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(candidate.to_text(), encoding="utf-8")
        if existing and existing.path and existing.path != target:
            existing.path.unlink(missing_ok=True)
        if predecessor is not None and predecessor.path is not None:
            predecessor.superseded_by = candidate.name
            predecessor.updated = now
            predecessor.path.write_text(predecessor.to_text(), encoding="utf-8")
        return candidate

    def correct(
        self,
        name: str,
        abstract: str | None = None,
        body: str | None = None,
        supersede_with: str | None = None,
        links: list[str] | None = None,
        valid_from: str | None = None,
        provenance: list[str] | None = None,
    ) -> MemoryRecord:
        current = self.find(name)
        if current is None or current.path is None:
            raise NotFoundError(f"no memory named {name}")
        if supersede_with:
            successor = self.find(supersede_with)
            if successor is None:
                raise NotFoundError(f"no memory named {supersede_with}")
            current.superseded_by = supersede_with
        if abstract is not None:
            current.abstract = abstract.strip()
        if body is not None:
            current.body = body
        if links is not None:
            current.links = list(links)
        if valid_from is not None:
            current.valid_from = valid_from
        current.updated = self.clock.timestamp()
        with store_lock(self.layout):
            for excerpt in provenance or []:
                stored = self.archive.append_provenance(current.name, excerpt, source=self.agent)
                current.provenance.append(str(stored.relative_to(self.root)))
        return self.write(current)

    def _predecessor(self, candidate: MemoryRecord, supersedes: str | None) -> MemoryRecord | None:
        if not supersedes:
            return None
        if supersedes == candidate.name:
            raise ValidationError([FieldError("supersedes", "cannot supersede itself")])
        found = self.find(supersedes)
        if found is None:
            raise NotFoundError(f"no memory named {supersedes}")
        record_module.validate(
            dataclasses.replace(found, superseded_by=candidate.name), self.config
        )
        return found

    def write(self, record: MemoryRecord) -> MemoryRecord:
        """Validate, persist, reproject. Agent writes and Manage rewrites share this path."""
        if record.path is None:
            raise NotFoundError(f"{record.name} has no location on disk")
        record_module.validate(record, self.config)
        record_module.canonicalise_dates(record)
        with store_lock(self.layout):
            record.path.write_text(record.to_text(), encoding="utf-8")
            self._project()
        return record

    def feedback(self, name: str, delta: float) -> MemoryRecord:
        current = self.find(name)
        if current is None or current.path is None:
            raise NotFoundError(f"no memory named {name}")
        current.weight = min(
            self.config.weight.ceiling, max(self.config.weight.floor, current.weight + delta)
        )
        return self.write(current)

    def retire(self, name: str) -> MemoryRecord:
        """Demotion into archive/. Reversible, non-destructive, and never automatic (T2)."""
        current = self.find(name)
        if current is None or current.path is None:
            raise NotFoundError(f"no memory named {name}")
        current.status = STATUS_RETIRED
        current.updated = self.clock.timestamp()
        with store_lock(self.layout):
            current.path.write_text(current.to_text(), encoding="utf-8")
            current.path = self.archive.retire(current.path, current.domain)
            self._project()
        return current

    def read(self, name: str, level: str = LEVEL_FULL) -> ReadResult:
        if level not in LEVELS:
            raise ValidationError([FieldError("level", f"must be one of {', '.join(LEVELS)}")])
        current = self.find(name)
        if current is None:
            raise NotFoundError(f"no memory named {name}")
        headings = tuple(
            entry.title for entry in chunking.outline(current.body, self.config)
        )
        if level == LEVEL_ABSTRACT:
            text = current.abstract
        elif level == LEVEL_OUTLINE:
            text = "\n".join(headings)
        else:
            text = current.body
        stamp = self.clock.now().isoformat()
        self._log_access([AccessEntry(stamp, name, "", KIND_READ, self.agent)])
        return ReadResult(record=current, level=level, text=text, outline=headings)

    def find(self, name: str) -> MemoryRecord | None:
        with self._database.connect() as connection:
            row = SearchIndex(connection).row(name)
        path = (self.root / str(row["path"])) if row else self._scan_for(name)
        if path is None or not path.exists():
            return None
        domain = self.layout.domain_of(path)
        if domain is None:
            return None
        return MemoryRecord.from_text(path.read_text(encoding="utf-8"), domain, path)

    def records(self, include_archived: bool = False) -> list[MemoryRecord]:
        paths = self.layout.truth_files()
        if include_archived:
            paths = paths + self.layout.archived_files()
        found: list[MemoryRecord] = []
        for path in paths:
            domain = self.layout.domain_of(path)
            if domain is None:
                continue
            found.append(MemoryRecord.from_text(path.read_text(encoding="utf-8"), domain, path))
        return found

    def sync_index(self) -> IndexReport:
        with store_lock(self.layout):
            return self._project()

    def rebuild_index(self) -> IndexReport:
        with store_lock(self.layout):
            report = self._indexer.rebuild()
            memory_md.write(self.layout, self.records())
            return report

    def _project(self) -> IndexReport:
        report = self._indexer.sync()
        memory_md.write(self.layout, self.records())
        return report

    def _log_access(self, entries: list[AccessEntry]) -> None:
        with self._database.connect() as connection:
            AccessLog(connection).append(entries)

    def _scan_for(self, name: str) -> pathlib.Path | None:
        for path in self.layout.truth_files() + self.layout.archived_files():
            if path.stem == name:
                return path
        return None

    def _target_path(
        self, candidate: MemoryRecord, topic: str | None, existing: MemoryRecord | None
    ) -> pathlib.Path:
        if existing is not None and existing.path is not None and topic is None:
            return existing.path
        folder = self.layout.domain_dir(candidate.domain)
        for part in (topic or "").split("/"):
            slug = slugify(part, self.config.storage.slug_max_length)
            if slug:
                folder = folder / slug
        return folder / (candidate.name + MEMORY_SUFFIX)

    def _reject_depth(self, target: pathlib.Path) -> None:
        relative = target.relative_to(self.root)
        depth_below_domain = len(relative.parts) - len(("domain", "file"))
        if depth_below_domain > self.config.storage.max_depth_below_domain:
            raise ValidationError(
                [FieldError("path", "exceeds max_depth_below_domain")]
            )


def _as_sequence(value: object) -> list[object]:
    return list(value) if isinstance(value, (list, tuple)) else []
