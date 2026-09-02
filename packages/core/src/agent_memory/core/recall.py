"""Eligibility before relevance, then relevance × weight × recency. Zero LLM (ADR-002)."""

from __future__ import annotations

import dataclasses
import datetime as dt
import sqlite3

from .access_log import KIND_RECALL, AccessEntry, AccessLog
from .config import Config
from .database import Database
from .raw_index import SOURCE_MEMORY, SOURCE_RAW, RawIndex
from .record import STATUS_RETIRED
from .search_index import SearchIndex
from .store import Store


@dataclasses.dataclass(frozen=True)
class Hit:
    name: str
    path: str
    abstract: str
    anchor: str
    heading: str
    domain: str
    type: str
    updated: str
    status: str
    weight: float
    relevance: float
    recency: float
    score: float
    source: str = SOURCE_MEMORY

    def as_dict(self) -> dict[str, object]:
        return dataclasses.asdict(self)


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
    ) -> list[Hit]:
        limit = limit or self._config.recall.default_limit
        if deep:
            limit *= self._config.recall.deep_limit_multiplier
        pool = limit * self._config.recall.candidate_pool_multiplier
        with self._database.connect() as connection:
            index = SearchIndex(connection)
            candidates = index.match(query, pool)
            eligible = self._eligible(index.rows(), scope=scope, as_of=as_of, deep=deep)
            hits = self._rank(candidates, eligible, as_of=as_of)
            if deep and self._config.recall.raw_enabled:
                hits = hits + self._raw_hits(RawIndex(connection), query, pool)
                hits.sort(key=lambda hit: (-hit.score, hit.name))
            hits = hits[:limit]
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
        deep: bool,
    ) -> dict[str, sqlite3.Row]:
        by_name = {str(row["name"]): row for row in rows}
        eligible: dict[str, sqlite3.Row] = {}
        for name, row in by_name.items():
            if not deep and int(row["archived"]):
                continue
            if not deep and str(row["status"]) == STATUS_RETIRED:
                continue
            if scope and not self._in_scope(str(row["path"]), scope):
                continue
            if as_of is None:
                if row["superseded_by"]:
                    continue
            else:
                if not self._current_at(row, by_name, as_of):
                    continue
            eligible[name] = row
        return eligible

    def _in_scope(self, path: str, scope: str) -> bool:
        return path.startswith(scope.strip("/"))

    def _current_at(self, row: sqlite3.Row, by_name: dict[str, sqlite3.Row], as_of: str) -> bool:
        if _as_date(str(row["valid_from"])) > _as_date(as_of):
            return False
        successor_name = row["superseded_by"]
        if not successor_name:
            return True
        successor = by_name.get(str(successor_name))
        if successor is None:
            return True
        return _as_date(str(successor["valid_from"])) > _as_date(as_of)

    def _rank(
        self,
        candidates: list,
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

        reference = _as_date(as_of) if as_of else self._store.clock.now().date()
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
                    domain=str(row["domain"]),
                    type=str(row["type"]),
                    updated=str(row["updated"]),
                    status=str(row["status"]),
                    weight=weight,
                    relevance=relevance,
                    recency=recency,
                    score=relevance * weight * recency,
                )
            )
        hits.sort(key=lambda hit: (-hit.score, hit.name))
        return hits

    def _raw_hits(self, raw: RawIndex, query: str, pool: int) -> list[Hit]:
        """Evidence, not knowledge: no weight, no recency, and deliberately outranked."""
        factor = self._config.recall.raw_relevance_factor
        found: list[Hit] = []
        for candidate in raw.match(query, pool):
            excerpt = candidate.text.strip().replace("\n", " ")
            found.append(
                Hit(
                    name=candidate.name,
                    path=str(self._store.root / candidate.path),
                    abstract=excerpt[: self._config.recall.snippet_max_chars],
                    anchor=candidate.anchor,
                    heading="",
                    domain="",
                    type=SOURCE_RAW,
                    updated="",
                    status="",
                    weight=0.0,
                    relevance=candidate.relevance,
                    recency=0.0,
                    score=candidate.relevance * factor,
                    source=SOURCE_RAW,
                )
            )
        return found

    def _kind_weight(self, kind: str) -> float:
        from .chunking import KIND_ABSTRACT

        if kind == KIND_ABSTRACT:
            return self._config.index.bm25_abstract_weight
        return self._config.index.bm25_body_weight

    def _recency(self, updated: str, reference: dt.date) -> float:
        age_days = max(0.0, (reference - _as_date(updated)).days)
        decayed = self._config.recall.recency_decay_base ** (
            age_days / self._config.recall.recency_half_life_days
        )
        return max(self._config.recall.recency_floor, decayed)


def _as_date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return dt.datetime.fromisoformat(value).date()
