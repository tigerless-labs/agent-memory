"""An ephemeral, deterministic navigation view over the current filesystem truth."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from . import timestamp
from .eligibility import eligible
from .errors import FieldError, NotFoundError, ValidationError
from .store import Store


@dataclasses.dataclass(frozen=True)
class Entry:
    name: str
    path: str
    abstract: str
    updated: str
    status: str
    relation: str


@dataclasses.dataclass(frozen=True)
class Overview:
    seed: str
    topic: str | None
    as_of: str | None
    entries: tuple[Entry, ...]
    truncated: bool

    def as_dict(self) -> dict[str, object]:
        return {
            **dataclasses.asdict(self),
            "entries": [dataclasses.asdict(entry) for entry in self.entries],
        }


def build(
    store: Store,
    seed: str,
    scope: str | None = None,
    as_of: str | None = None,
    limit: int | None = None,
) -> Overview:
    """Seed first, exact topic siblings next, then outgoing links; never recursive.

    Read truth directly so edits, moves and retirement are visible without index sync.
    Bodies are parsed by Store.records but never returned, opened through Store.read,
    or logged as reads. Validity intervals include invalid records for historical views before
    restricting the neighborhood.
    """
    limit = store.config.recall.default_limit if limit is None else limit
    if limit < 1:
        raise ValidationError([FieldError("limit", "must be positive")])
    if as_of is not None and not timestamp.is_valid(as_of):
        raise ValidationError(
            [FieldError("as_of", "must be an ISO 8601 day or zone-aware instant")]
        )
    records = {record.name: record for record in store.records(include_invalid=True)}
    if seed not in records:
        raise NotFoundError(f"no memory named {seed}")
    rows = [
        {
            **record.frontmatter_fields(),
            "path": str(record.path.relative_to(store.root)),
        }
        for record in records.values()
        if record.path is not None
    ]
    allowed = eligible(rows, scope=scope, as_of=as_of, deep=False)
    if seed not in allowed:
        raise ValidationError([FieldError("seed", "not eligible for this scope/as-of view")])
    parent = Path(str(allowed[seed]["path"])).parent
    # A domain root is a type bucket, not a topic. Never expand it as a neighborhood.
    topic = str(parent) if len(parent.parts) > 1 else None
    links = set(records[seed].links)
    neighbors: list[tuple[int, str, str]] = []
    for name, row in allowed.items():
        if name == seed:
            continue
        if topic and Path(str(row["path"])).parent == parent:
            neighbors.append((0, name, "same-topic"))
        elif name in links:
            neighbors.append((1, name, "link"))
    ordered = [(seed, "seed")] + [(name, relation) for _, name, relation in sorted(neighbors)]
    entries = tuple(
        Entry(
            name=name,
            path=str(allowed[name]["path"]),
            abstract=str(allowed[name]["abstract"])[:store.config.storage.abstract_max_chars],
            updated=str(allowed[name]["updated"]),
            status=str(allowed[name]["status"]),
            relation=relation,
        )
        for name, relation in ordered[:limit]
    )
    return Overview(seed, topic, as_of, entries, truncated=len(ordered) > limit)
