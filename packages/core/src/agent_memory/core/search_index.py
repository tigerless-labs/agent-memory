"""BM25 over abstract + body (ADR-003). Projection only: never a source of truth."""

from __future__ import annotations

import dataclasses
import re
import sqlite3

from .chunking import Chunk
from .database import SURFACE_ACTIVE, SURFACE_HISTORY
from .record import MemoryRecord

_TOKENS = re.compile(r"[0-9A-Za-z_]+")
LINK_SEPARATOR = ","
SURFACES = (SURFACE_ACTIVE, SURFACE_HISTORY)


@dataclasses.dataclass(frozen=True)
class Candidate:
    name: str
    kind: str
    anchor: str
    heading: str
    relevance: float


def to_match_query(query: str) -> str:
    tokens = [token.lower() for token in _TOKENS.findall(query)]
    return " OR ".join(f'"{token}"' for token in dict.fromkeys(tokens))


class SearchIndex:
    def __init__(self, connection: sqlite3.Connection):
        self._connection = connection

    def upsert(self, record: MemoryRecord, chunks: list[Chunk], relative_path: str) -> None:
        self.remove(record.name)
        self._connection.execute(
            "INSERT INTO records(name, path, type, abstract, status, created, updated, "
            "valid_from, invalid_at, superseded_by, weight, author, links, provenance) "
            "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record.name,
                relative_path,
                record.type,
                record.abstract,
                record.status,
                record.created,
                record.updated,
                record.valid_from or record.created,
                record.invalid_at,
                record.superseded_by,
                float(record.weight),
                record.author,
                LINK_SEPARATOR.join(record.links),
                LINK_SEPARATOR.join(record.provenance),
            ),
        )
        surface = SURFACE_ACTIVE if record.is_active() else SURFACE_HISTORY
        self._connection.executemany(
            f"INSERT INTO {surface}(name, kind, anchor, heading, text) VALUES(?, ?, ?, ?, ?)",
            [
                (record.name, chunk.kind, chunk.anchor, chunk.heading, chunk.text)
                for chunk in chunks
            ],
        )

    def remove(self, name: str) -> None:
        self._connection.execute("DELETE FROM records WHERE name = ?", (name,))
        for surface in SURFACES:
            self._connection.execute(f"DELETE FROM {surface} WHERE name = ?", (name,))

    def remove_path(self, path: str) -> None:
        rows = self._connection.execute(
            "SELECT name FROM records WHERE path = ?", (path,)
        ).fetchall()
        for row in rows:
            self.remove(row["name"])

    def rows(self, include_invalid: bool = True) -> list[sqlite3.Row]:
        if include_invalid:
            return self._connection.execute("SELECT * FROM records").fetchall()
        return self._connection.execute("SELECT * FROM records WHERE invalid_at IS NULL").fetchall()

    def row(self, name: str) -> sqlite3.Row | None:
        return self._connection.execute("SELECT * FROM records WHERE name = ?", (name,)).fetchone()

    def match(self, query: str, pool: int, surface: str = SURFACE_ACTIVE) -> list[Candidate]:
        if surface not in SURFACES:
            raise ValueError(f"unknown surface {surface}")
        expression = to_match_query(query)
        if not expression:
            return []
        rows = self._connection.execute(
            f"SELECT name, kind, anchor, heading, bm25({surface}) AS rank FROM {surface} "
            f"WHERE {surface} MATCH ? ORDER BY rank LIMIT ?",
            (expression, pool),
        ).fetchall()
        return [
            Candidate(
                name=row["name"],
                kind=row["kind"],
                anchor=row["anchor"],
                heading=row["heading"],
                relevance=-float(row["rank"]),
            )
            for row in rows
        ]
