"""Eligibility before relevance, then relevance × weight × recency. Zero LLM (ADR-002).

The default surface holds active files only. `--as-of` is the one reader of the history
surface, and it judges a file by its validity interval, never by its text alone.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import sqlite3

from . import timestamp
from .access_log import KIND_RECALL, AccessEntry, AccessLog
from .config import Config
from .database import SURFACE_ACTIVE, SURFACE_HISTORY, Database
from .raw_index import SOURCE_MEMORY, SOURCE_RAW, RawIndex
from .search_index import LINK_SEPARATOR, Candidate, SearchIndex
from .sessions import Pointer, parse_pointer
from .store import Store


@dataclasses.dataclass(frozen=True)
class Hit:
    name: str
    path: str
    abstract: str
    anchor: str
    heading: str
    type: str
    updated: str
    status: str
    weight: float
    relevance: float
    recency: float
    score: float
    source: str = SOURCE_MEMORY
    provenance: tuple[str, ...] = ()
    cited_by: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        payload = dataclasses.asdict(self)
        payload["provenance"] = list(self.provenance)
        payload["cited_by"] = list(self.cited_by)
        return payload


class Recall:
    def __init__(self, store: Store):
        self._store = store
        self._config: Config = store.config
        self._database = Database(store.layout)

    def recall(
        self,
        query: str,
        scope: str | None = None,
        as_of: str | None = None,
        deep: bool = False,
        limit: int | None = None,
        log: bool = True,
    ) -> list[Hit]:
        limit = limit or self._config.recall.default_limit
        if deep:
            limit *= self._config.recall.deep_limit_multiplier
        pool = limit * self._config.recall.candidate_pool_multiplier
        with self._database.connect() as connection:
            index = SearchIndex(connection)
            candidates = index.match(query, pool, SURFACE_ACTIVE)
            if as_of is not None:
                candidates = candidates + index.match(query, pool, SURFACE_HISTORY)
            eligible = self._eligible(index.rows(), scope=scope, as_of=as_of)
            hits = self._rank(candidates, eligible, as_of=as_of)
            if deep and self._config.recall.raw_enabled:
                citations = self._citations(index.rows())
                hits = hits + self._raw_hits(RawIndex(connection), query, pool, citations)
                hits.sort(key=lambda hit: (-hit.score, hit.name))
            hits = hits[:limit]
            if not log:
                return hits
            AccessLog(connection).append(
                [
                    AccessEntry(
                        self._store.clock.now().isoformat(),
                        hit.name,
                        query,
                        KIND_RECALL,
                        self._store.agent,
                    )
                    for hit in hits
                ]
            )
        return hits

    def _eligible(
        self,
        rows: list[sqlite3.Row],
        scope: str | None,
        as_of: str | None,
    ) -> dict[str, sqlite3.Row]:
        eligible: dict[str, sqlite3.Row] = {}
        moment = timestamp.parse(as_of) if as_of else None
        for row in rows:
            name = str(row["name"])
            if scope and not self._in_scope(str(row["path"]), scope):
                continue
            if moment is None:
                if row["invalid_at"]:
                    continue
            elif not self._current_at(row, moment):
                continue
            eligible[name] = row
        return eligible

    def _in_scope(self, path: str, scope: str) -> bool:
        return path.startswith(scope.strip("/"))

    def _current_at(self, row: sqlite3.Row, moment: dt.datetime) -> bool:
        if timestamp.parse(str(row["valid_from"])) > moment:
            return False
        ended = row["invalid_at"]
        return not (ended and timestamp.parse(str(ended)) <= moment)

    def _rank(
        self,
        candidates: list[Candidate],
        eligible: dict[str, sqlite3.Row],
        as_of: str | None,
    ) -> list[Hit]:
        best: dict[str, tuple[float, str, str]] = {}
        for candidate in candidates:
            if candidate.name not in eligible:
                continue
            weighted = candidate.relevance * self._kind_weight(candidate.kind)
            current = best.get(candidate.name)
            if current is None or weighted > current[0]:
                best[candidate.name] = (weighted, candidate.anchor, candidate.heading)

        reference = timestamp.parse(as_of) if as_of else self._store.clock.now()
        hits: list[Hit] = []
        for name, (relevance, anchor, heading) in best.items():
            row = eligible[name]
            recency = self._recency(str(row["updated"]), reference)
            weight = float(row["weight"])
            hits.append(
                Hit(
                    name=name,
                    path=str(self._store.root / str(row["path"])),
                    abstract=str(row["abstract"]),
                    anchor=anchor,
                    heading=heading,
                    type=str(row["type"]),
                    updated=str(row["updated"]),
                    status=str(row["status"]),
                    weight=weight,
                    relevance=relevance,
                    recency=recency,
                    score=relevance * weight * recency,
                    provenance=tuple(
                        item for item in str(row["provenance"]).split(LINK_SEPARATOR) if item
                    ),
                )
            )
        hits.sort(key=lambda hit: (-hit.score, hit.name))
        return hits

    def _citations(self, rows: list[sqlite3.Row]) -> list[tuple[Pointer, str]]:
        cited: list[tuple[Pointer, str]] = []
        for row in rows:
            for item in str(row["provenance"]).split(LINK_SEPARATOR):
                pointer = parse_pointer(item)
                if pointer is not None:
                    cited.append((pointer, str(row["name"])))
        return cited

    def _raw_hits(
        self,
        raw: RawIndex,
        query: str,
        pool: int,
        citations: list[tuple[Pointer, str]],
    ) -> list[Hit]:
        """Evidence, not knowledge: no weight, no recency, and deliberately outranked."""
        factor = self._config.recall.raw_relevance_factor
        found: list[Hit] = []
        for candidate in raw.match(query, pool):
            excerpt = candidate.text.strip().replace("\n", " ")
            pointer = parse_pointer(candidate.name)
            cited_by = tuple(
                sorted({name for cited, name in citations if pointer and cited.overlaps(pointer)})
            )
            found.append(
                Hit(
                    name=candidate.name,
                    path=str(self._store.root / candidate.path),
                    abstract=excerpt[: self._config.recall.snippet_max_chars],
                    anchor=candidate.anchor,
                    heading="",
                    type=SOURCE_RAW,
                    updated="",
                    status="",
                    weight=0.0,
                    relevance=candidate.relevance,
                    recency=0.0,
                    score=candidate.relevance * factor,
                    source=SOURCE_RAW,
                    cited_by=cited_by,
                )
            )
        return found

    def _kind_weight(self, kind: str) -> float:
        from .chunking import KIND_ABSTRACT

        if kind == KIND_ABSTRACT:
            return self._config.index.bm25_abstract_weight
        return self._config.index.bm25_body_weight

    def _recency(self, updated: str, reference: dt.datetime) -> float:
        age_days = max(0.0, timestamp.days_between(reference, timestamp.parse(updated)))
        decayed = self._config.recall.recency_decay_base ** (
            age_days / self._config.recall.recency_half_life_days
        )
        return max(self._config.recall.recency_floor, decayed)
