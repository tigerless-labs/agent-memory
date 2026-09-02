"""Retrieval over raw material.

Invariant 4 promises that anything the distiller misses stays recoverable. Keeping the
transcript on disk is only half of that promise — this is the half that lets a query reach it.
Raw material stays off the default surface and answers only to `--deep`, because it is
evidence, not knowledge.
"""

from __future__ import annotations

import dataclasses
import pathlib
import sqlite3

from .search_index import to_match_query

SOURCE_RAW = "raw"
SOURCE_MEMORY = "memory"
ANCHOR_SEPARATOR = "#"
PARAGRAPH_BREAK = "\n"


@dataclasses.dataclass(frozen=True)
class RawHit:
    name: str
    path: str
    anchor: str
    text: str
    relevance: float


class RawIndex:
    def __init__(self, connection: sqlite3.Connection):
        self._connection = connection

    def remove(self, path: str) -> None:
        self._connection.execute("DELETE FROM raw_chunks WHERE path = ?", (path,))

    def upsert(self, path: str, name: str, text: str, chunk_chars: int) -> int:
        self.remove(path)
        chunks = split(text, chunk_chars)
        self._connection.executemany(
            "INSERT INTO raw_chunks(name, path, anchor, text) VALUES(?, ?, ?, ?)",
            [
                (f"{name}{ANCHOR_SEPARATOR}{index}", path, str(index), chunk)
                for index, chunk in enumerate(chunks)
            ],
        )
        return len(chunks)

    def match(self, query: str, pool: int) -> list[RawHit]:
        expression = to_match_query(query)
        if not expression:
            return []
        rows = self._connection.execute(
            "SELECT name, path, anchor, text, bm25(raw_chunks) AS rank FROM raw_chunks "
            "WHERE raw_chunks MATCH ? ORDER BY rank LIMIT ?",
            (expression, pool),
        ).fetchall()
        return [
            RawHit(
                name=str(row["name"]),
                path=str(row["path"]),
                anchor=str(row["anchor"]),
                text=str(row["text"]),
                relevance=-float(row["rank"]),
            )
            for row in rows
        ]


def split(text: str, chunk_chars: int) -> list[str]:
    lines = [line for line in text.splitlines() if line.strip()]
    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for line in lines:
        if current and size + len(line) > chunk_chars:
            chunks.append(PARAGRAPH_BREAK.join(current))
            current = []
            size = 0
        current.append(line)
        size += len(line)
    if current:
        chunks.append(PARAGRAPH_BREAK.join(current))
    return chunks


def source_name(path: pathlib.Path) -> str:
    return path.stem
