"""The single write path (Invariant 2). Every adapter, and Manage itself, enters here.

A write names a type and fills that type's fields; the store derives the path (ADR-008),
decides update versus replacement (ADR-009), and reprojects. Nothing here deletes a file.
"""

from __future__ import annotations

import dataclasses
import pathlib

from . import chunking, memory_md, placement
from . import record as record_module
from .access_log import KIND_READ, AccessEntry, AccessLog
from .archive import Archive
from .clock import Clock
from .config import Config, resolve_store_root
from .database import Database
from .errors import FieldError, NotFoundError, ValidationError
from .indexer import Indexer, IndexReport
from .locking import store_lock
from .paths import StoreLayout
from .record import MemoryRecord
from .schema import MODE_ADD_ONLY, MemorySchema, SchemaRegistry
from .search_index import SearchIndex

LEVEL_ABSTRACT = "abstract"
LEVEL_OUTLINE = "outline"
LEVEL_FULL = "full"
LEVELS = (LEVEL_ABSTRACT, LEVEL_OUTLINE, LEVEL_FULL)
UNKNOWN_AGENT = "unknown"

RECORD_FIELDS = frozenset(
    {
        "abstract", "type", "fields", "body", "name", "author", "links",
        "valid_from", "provenance", "weight", "supersedes", "create_group",
    }
)
UPDATABLE_IN_PLACE = ("abstract", "links", "weight", "provenance")


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
    ):
        self.root = resolve_store_root(root)
        self.config = config or Config.load(self.root)
        self.layout = StoreLayout(self.root, self.config)
        self.clock = clock or Clock()
        self.agent = agent
        self.archive = Archive(self.layout, self.clock)
        self.schemas = SchemaRegistry(self.layout)
        self._indexer = Indexer(self.layout, self.clock)
        self._database = Database(self.layout)

    def init(self) -> StoreLayout:
        self.layout.ensure()
        self.schemas.ensure_factory()
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
        self.schemas.ensure_factory()
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
        schema = self.schemas.require(str(spec.get("type") or ""))
        if not str(spec.get("abstract") or "").strip():
            raise ValidationError([FieldError("abstract", "required")])
        now = self.clock.timestamp()
        valid_from = str(spec.get("valid_from") or "") or None
        placed = placement.resolve(
            schema,
            _as_mapping(spec.get("fields")),
            self.config,
            self.layout.groups_of(schema.type),
            valid_from=valid_from,
            now=now,
            name=str(spec["name"]) if spec.get("name") else None,
            create_group=bool(spec.get("create_group")),
            fallback=str(spec.get("abstract") or "") or None,
        )
        target = self.root / placed.relative_path
        existing = self._at(target)
        moved_from: pathlib.Path | None = None
        if existing is None:
            elsewhere = self.find(placed.name)
            if elsewhere is not None and elsewhere.path is not None:
                existing, moved_from = elsewhere, elsewhere.path
        if existing is not None and schema.mode == MODE_ADD_ONLY:
            placed = dataclasses.replace(
                placed,
                name=f"{placed.name}-{self.clock.stamp().lower()}",
                relative_path=placed.relative_path.with_name(
                    f"{placed.name}-{self.clock.stamp().lower()}{placed.relative_path.suffix}"
                ),
            )
            target = self.root / placed.relative_path
            existing = None
        elif existing is not None and not existing.is_active():
            raise ValidationError(
                [FieldError("name", f"{existing.name} is invalid; supersede it instead")]
            )

        supersedes = str(spec.get("supersedes") or "") or None
        weight = spec.get("weight")
        candidate = MemoryRecord(
            name=placed.name,
            abstract=str(spec.get("abstract") or "").strip(),
            type=schema.type,
            author=str(spec.get("author") or self.agent),
            created=existing.created if existing else now,
            updated=now,
            body=str(spec.get("body") or ""),
            valid_from=valid_from or (existing.valid_from if existing else now),
            weight=float(str(weight)) if weight is not None else self.config.weight.initial,
            links=[str(link) for link in _as_sequence(spec.get("links"))],
            provenance=list(existing.provenance) if existing else [],
            fields=dict(placed.fields),
            path=target,
        )
        if existing is not None and supersedes is None:
            self._enforce_update_only(existing, candidate)
        record_module.validate(candidate, self.config, schema)
        record_module.canonicalise_dates(candidate)
        predecessor = self._predecessor(candidate, supersedes)

        for excerpt in _as_sequence(spec.get("provenance")):
            candidate.provenance.append(self._store_provenance(candidate.name, str(excerpt)))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(candidate.to_text(), encoding="utf-8")
        if moved_from is not None and moved_from != target:
            moved_from.unlink(missing_ok=True)
        if predecessor is not None and predecessor.path is not None:
            record_module.invalidate(predecessor, candidate.valid_from or now, candidate.name)
            predecessor.updated = now
            predecessor.path.write_text(predecessor.to_text(), encoding="utf-8")
        return candidate

    def _enforce_update_only(self, existing: MemoryRecord, candidate: MemoryRecord) -> None:
        """An in-place write may change how a fact is described, never the fact itself."""
        if candidate.body.strip() and candidate.body.strip() != existing.body.strip():
            raise ValidationError(
                [FieldError("body", "the fact changed: write a successor with supersedes")]
            )
        if not candidate.body.strip():
            candidate.body = existing.body
        if not candidate.links:
            candidate.links = list(existing.links)

    def _store_provenance(self, name: str, item: str) -> str:
        if _looks_like_pointer(item):
            return item
        stored = self.archive.append_provenance(name, item, source=self.agent)
        return str(stored.relative_to(self.root))

    def _predecessor(self, candidate: MemoryRecord, supersedes: str | None) -> MemoryRecord | None:
        if not supersedes:
            return None
        if supersedes == candidate.name:
            raise ValidationError([FieldError("supersedes", "cannot supersede itself")])
        found = self.find(supersedes)
        if found is None:
            raise NotFoundError(f"no memory named {supersedes}")
        if not found.is_active():
            raise ValidationError([FieldError("supersedes", f"{supersedes} is already invalid")])
        return found

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
        now = self.clock.timestamp()
        if supersede_with:
            successor = self.find(supersede_with)
            if successor is None:
                raise NotFoundError(f"no memory named {supersede_with}")
            record_module.invalidate(current, successor.valid_from or now, supersede_with)
        if abstract is not None:
            current.abstract = abstract.strip()
        if body is not None:
            current.body = body
        if links is not None:
            current.links = list(links)
        if valid_from is not None:
            current.valid_from = valid_from
        current.updated = now
        with store_lock(self.layout):
            for excerpt in provenance or []:
                current.provenance.append(self._store_provenance(current.name, excerpt))
        return self.write(current)

    def delete(self, name: str) -> MemoryRecord:
        """Marks the record invalid. The file stays; physical removal is a human command."""
        current = self.find(name)
        if current is None or current.path is None:
            raise NotFoundError(f"no memory named {name}")
        if not current.is_active():
            return current
        now = self.clock.timestamp()
        record_module.invalidate(current, now)
        current.updated = now
        return self.write(current)

    def write(self, record: MemoryRecord) -> MemoryRecord:
        """Validate, persist, reproject. Agent writes and Manage rewrites share this path."""
        if record.path is None:
            raise NotFoundError(f"{record.name} has no location on disk")
        record_module.validate(record, self.config, self.schemas.get(record.type))
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
        return self._at(path) if path is not None else None

    def records(self, include_invalid: bool = False) -> list[MemoryRecord]:
        found: list[MemoryRecord] = []
        for path in self.layout.truth_files():
            record = self._at(path)
            if record is None:
                continue
            if include_invalid or record.is_active():
                found.append(record)
        return found

    def schema_of(self, record: MemoryRecord) -> MemorySchema | None:
        return self.schemas.get(record.type)

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

    def _at(self, path: pathlib.Path | None) -> MemoryRecord | None:
        if path is None or not path.exists() or self.layout.type_of(path) is None:
            return None
        return MemoryRecord.from_text(path.read_text(encoding="utf-8"), path)

    def _scan_for(self, name: str) -> pathlib.Path | None:
        for path in self.layout.truth_files():
            if path.stem == name:
                return path
        return None


def _as_sequence(value: object) -> list[object]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _as_mapping(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, dict) else {}


def _looks_like_pointer(item: str) -> bool:
    return "#" in item and "/" in item and "\n" not in item and " " not in item.strip()
