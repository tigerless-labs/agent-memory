"""BM25 over abstract + body (ADR-003). Projection only: never a source of truth."""

from __future__ import annotations

import dataclasses
import re
import sqlite3

from .chunking import Chunk
from .record import MemoryRecord

_TOKENS = re.compile(r"[0-9A-Za-z_]+")
LINK_SEPARATOR = ","


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

    def upsert(
        self, record: MemoryRecord, chunks: list[Chunk], archived: bool, relative_path: str
    ) -> None:
        self.remove(record.name)
        self._connection.execute(
            "INSERT INTO records(name, path, domain, type, abstract, status, created, updated, "
            "valid_from, superseded_by, weight, author, links, archived) "
            "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record.name,
                relative_path,
                record.domain,
                record.type,
                record.abstract,
                record.status,
                record.created,
                record.updated,
                record.valid_from or record.created,
                record.superseded_by,
                float(record.weight),
                record.author,
                LINK_SEPARATOR.join(record.links),
                int(archived),
            ),
        )
        self._connection.executemany(
            "INSERT INTO chunks(name, kind, anchor, heading, text) VALUES(?, ?, ?, ?, ?)",
            [
                (record.name, chunk.kind, chunk.anchor, chunk.heading, chunk.text)
                for chunk in chunks
            ],
        )

    def remove(self, name: str) -> None:
        self._connection.execute("DELETE FROM records WHERE name = ?", (name,))
        self._connection.execute("DELETE FROM chunks WHERE name = ?", (name,))

    def remove_path(self, path: str) -> None:
        rows = self._connection.execute(
            "SELECT name FROM records WHERE path = ?", (path,)
        ).fetchall()
        for row in rows:
            self.remove(row["name"])

    def rows(self, include_archived: bool = True) -> list[sqlite3.Row]:
        if include_archived:
            return self._connection.execute("SELECT * FROM records").fetchall()
        return self._connection.execute("SELECT * FROM records WHERE archived = 0").fetchall()

    def row(self, name: str) -> sqlite3.Row | None:
        return self._connection.execute("SELECT * FROM records WHERE name = ?", (name,)).fetchone()

    def match(self, query: str, pool: int) -> list[Candidate]:
        expression = to_match_query(query)
        if not expression:
            return []
        rows = self._connection.execute(
            "SELECT name, kind, anchor, heading, bm25(chunks) AS rank FROM chunks "
            "WHERE chunks MATCH ? ORDER BY rank LIMIT ?",
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
