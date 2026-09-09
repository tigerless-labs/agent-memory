"""The single write path (Invariant 2). Every adapter, and Manage itself, enters here.

A write names a type and fills that type's fields; the store derives the path (ADR-008),
decides update versus replacement (ADR-009), and reprojects. Nothing here deletes a file.
"""

from __future__ import annotations

import dataclasses
import pathlib
import tempfile

from . import chunking, memory_md, placement, timestamp
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
from .sessions import Message, parse_pointer, resolve

LEVEL_ABSTRACT = "abstract"
LEVEL_OUTLINE = "outline"
LEVEL_FULL = "full"
FIRST_SUCCESSOR_ORDINAL = 2
LEVELS = (LEVEL_ABSTRACT, LEVEL_OUTLINE, LEVEL_FULL)
UNKNOWN_AGENT = "unknown"

RECORD_FIELDS = frozenset(
    {
        "abstract",
        "type",
        "fields",
        "body",
        "name",
        "author",
        "links",
        "valid_from",
        "provenance",
        "weight",
        "supersedes",
        "create_group",
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
        if not specs:
            return BatchResult(written=written, rejected=rejected)
        with store_lock(self.layout):
            for index, spec in enumerate(specs):
                try:
                    written.append(self._write_one(_known_fields(spec)))
                except ValidationError as error:
                    rejected.append(Rejected(index=index, errors=list(error.errors)))
            self._project()
        return BatchResult(written=written, rejected=rejected)

    def _write_one(self, spec: dict[str, object]) -> MemoryRecord:
        """One malformed item is one rejection: a batch is many memories, and the rest of
        them reaching disk is what keeps a single stray key from costing a conversation."""
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
        supersedes = str(spec.get("supersedes") or "") or None
        derived_name = not spec.get("name")
        if supersedes and derived_name and self.find(placed.name) is not None:
            placed = self._successor_placement(placed)
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
        self._validate_links(candidate, existing)
        predecessor = self._predecessor(candidate, supersedes)

        for excerpt in _as_sequence(spec.get("provenance")):
            pointer = self._store_provenance(candidate.name, str(excerpt))
            if pointer not in candidate.provenance:
                candidate.provenance.append(pointer)
        self._reject_facts_dated_after_their_evidence(candidate)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(candidate.to_text(), encoding="utf-8")
        if moved_from is not None and moved_from != target:
            moved_from.unlink(missing_ok=True)
        if predecessor is not None and predecessor.path is not None:
            record_module.invalidate(predecessor, candidate.valid_from or now, candidate.name)
            predecessor.updated = now
            self._persist(predecessor)
        return candidate

    def _successor_placement(self, placed: placement.Placement) -> placement.Placement:
        """A successor with the same key as its predecessor keeps the key and takes the next
        free ordinal; the predecessor keeps its name, so nothing that cites it breaks."""
        ordinal = FIRST_SUCCESSOR_ORDINAL
        while True:
            name = f"{placed.name}-{ordinal}"
            path = placed.relative_path.with_name(f"{name}{placed.relative_path.suffix}")
            if self.find(name) is None and not (self.root / path).exists():
                return dataclasses.replace(placed, name=name, relative_path=path)
            ordinal += 1

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
        if parse_pointer(item) is not None:
            return item.strip()
        stored = self.archive.append_provenance(name, item, source=self.agent)
        return str(stored.relative_to(self.root))

    def _reject_facts_dated_after_their_evidence(self, record: MemoryRecord) -> None:
        """A fact cannot hold from later than the conversation that stated it."""
        if not record.valid_from:
            return
        stated = [message.at for message in self.trace_record(record) if message.at]
        if not stated:
            return
        latest = max(timestamp.parse(at) for at in stated)
        if timestamp.parse(record.valid_from) > latest:
            raise ValidationError(
                [FieldError("valid_from", "later than the messages this memory cites")]
            )

    def trace(self, name: str, *, include_invalid: bool = False) -> list[Message]:
        """Opens the messages a memory cites. The one read that reaches raw material by pointer."""
        current = self._readable(name, include_invalid)
        stamp = self.clock.now().isoformat()
        self._log_access([AccessEntry(stamp, name, "", KIND_READ, self.agent)])
        return self.trace_record(current)

    def trace_record(self, record: MemoryRecord) -> list[Message]:
        messages: list[Message] = []
        for item in record.provenance:
            pointer = parse_pointer(item)
            if pointer is not None:
                messages.extend(resolve(self.layout, pointer))
        return messages

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
        with store_lock(self.layout):
            current = self.find(name)
            if current is None or current.path is None:
                raise NotFoundError(f"no memory named {name}")
            if not current.is_active():
                raise ValidationError(
                    [FieldError("status", "correction requires an active memory")]
                )
            now = self.clock.timestamp()
            if supersede_with:
                successor = self.find(supersede_with)
                if successor is None:
                    raise NotFoundError(f"no memory named {supersede_with}")
                if not successor.is_active():
                    raise ValidationError(
                        [FieldError("supersede_with", "successor must be active")]
                    )
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
            self._validate_write(current)
            for excerpt in provenance or []:
                current.provenance.append(self._store_provenance(current.name, excerpt))
            self._persist(current)
            self._project()
            return current

    def delete(self, name: str) -> MemoryRecord:
        """Invalidate and archive one memory; retry completes archival and projection."""
        with store_lock(self.layout):
            current = self.find(name)
            if current is None or current.path is None:
                raise NotFoundError(f"no memory named {name}")
            if current.is_active():
                now = self.clock.timestamp()
                record_module.invalidate(current, now)
                current.updated = now
            self._validate_write(current)
            self._persist(current)
            self._project()
            return current

    def gc(self) -> list[str]:
        """Physically removes invalid files. A human runs this; Manage cannot reach it."""
        removed: list[str] = []
        with store_lock(self.layout):
            for record in self.records(include_invalid=True):
                if record.is_active() or record.path is None:
                    continue
                record.path.unlink(missing_ok=True)
                removed.append(record.name)
            self._project()
        return removed

    def write(self, record: MemoryRecord) -> MemoryRecord:
        """Validate, persist, reproject. Agent writes and Manage rewrites share this path."""
        with store_lock(self.layout):
            self._validate_write(record)
            self._persist(record)
            self._project()
        return record

    def _validate_write(self, record: MemoryRecord) -> None:
        if record.path is None or self.layout.type_of(record.path) != record.type:
            raise ValidationError([FieldError("path", "memory must belong to this store")])
        existing = self.find(record.name)
        if record.is_active() and (
            self.layout.is_archived_memory(record.path)
            or (existing is not None and not existing.is_active())
        ):
            raise ValidationError([FieldError("status", "an invalid memory cannot be reactivated")])
        record_module.validate(record, self.config, self.schemas.get(record.type))
        record_module.canonicalise_dates(record)
        self._validate_links(record, existing)

    def _validate_links(self, record: MemoryRecord, existing: MemoryRecord | None) -> None:
        added = set(record.links) - set(existing.links if existing else [])
        for name in sorted(added):
            target = self.find(name)
            if name == record.name or target is None or not target.is_active():
                raise ValidationError(
                    [FieldError("links", f"{name} must name another active memory")]
                )

    def _persist(self, record: MemoryRecord) -> None:
        if record.path is None:
            raise NotFoundError(f"{record.name} has no location on disk")
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=record.path.parent, delete=False
        ) as handle:
            temporary = pathlib.Path(handle.name)
            try:
                handle.write(record.to_text())
                handle.flush()
                temporary.replace(record.path)
            finally:
                temporary.unlink(missing_ok=True)
        if not record.is_active():
            self.archive.archive_memory(record)

    def feedback(self, name: str, delta: float) -> MemoryRecord:
        current = self.find(name)
        if current is None or current.path is None:
            raise NotFoundError(f"no memory named {name}")
        current.weight = min(
            self.config.weight.ceiling, max(self.config.weight.floor, current.weight + delta)
        )
        return current

    def read(
        self, name: str, level: str = LEVEL_FULL, *, include_invalid: bool = False
    ) -> ReadResult:
        if level not in LEVELS:
            raise ValidationError([FieldError("level", f"must be one of {', '.join(LEVELS)}")])
        current = self._readable(name, include_invalid)
        headings = tuple(entry.title for entry in chunking.outline(current.body, self.config))
        if level == LEVEL_ABSTRACT:
            text = current.abstract
        elif level == LEVEL_OUTLINE:
            text = "\n".join(headings)
        else:
            text = current.body
        stamp = self.clock.now().isoformat()
        self._log_access([AccessEntry(stamp, name, "", KIND_READ, self.agent)])
        return ReadResult(record=current, level=level, text=text, outline=headings)

    def _readable(self, name: str, include_invalid: bool) -> MemoryRecord:
        current = self.find(name)
        if current is None or (
            not include_invalid
            and (
                not current.is_active()
                or (current.path is not None and self.layout.is_archived_memory(current.path))
            )
        ):
            raise NotFoundError(
                f"no active memory named {name}; use explicit history for invalid memories"
            )
        return current

    def find(self, name: str) -> MemoryRecord | None:
        with self._database.connect() as connection:
            row = SearchIndex(connection).row(name)
        path = (self.root / str(row["path"])) if row else self._scan_for(name)
        found = self._at(path) if path is not None else None
        return found if found is not None else self._at(self._scan_for(name))

    def records(self, include_invalid: bool = False) -> list[MemoryRecord]:
        found: list[MemoryRecord] = []
        for path in self.layout.truth_files(include_archive=include_invalid):
            record = self._at(path)
            if record is None:
                continue
            if include_invalid or (record.is_active() and not self.layout.is_archived_memory(path)):
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
        memory_md.write(self.layout, self.records())
        report = self._indexer.sync()
        return report

    def _log_access(self, entries: list[AccessEntry]) -> None:
        with self._database.connect() as connection:
            AccessLog(connection).append(entries)

    def _at(self, path: pathlib.Path | None) -> MemoryRecord | None:
        if path is None or not path.exists() or self.layout.type_of(path) is None:
            return None
        return MemoryRecord.from_text(path.read_text(encoding="utf-8"), path)

    def _scan_for(self, name: str) -> pathlib.Path | None:
        for path in self.layout.truth_files(include_archive=True):
            if path.stem == name:
                return path
        return None


def _known_fields(spec: dict[str, object]) -> dict[str, object]:
    unknown = sorted(set(spec) - RECORD_FIELDS)
    if unknown:
        raise ValidationError([FieldError("spec", f"unknown field: {', '.join(unknown)}")])
    return spec


def _as_sequence(value: object) -> list[object]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _as_mapping(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, dict) else {}
