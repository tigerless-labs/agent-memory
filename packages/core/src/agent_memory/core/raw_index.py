"""Retrieval over raw material.

Invariant 4 promises that anything the distiller misses stays recoverable. Keeping the
transcript on disk is only half of that promise — this is the half that lets a query reach it.
Raw material stays off the default surface and answers only to `--deep`, because it is
evidence, not knowledge. Every hit names a message range, so it can be cited and traced.
"""

from __future__ import annotations

import dataclasses
import sqlite3

from .search_index import to_match_query
from .sessions import Message, Pointer, render_pointer

SOURCE_RAW = "raw"
SOURCE_MEMORY = "memory"
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

    def upsert(self, path: str, session: str, messages: list[Message], chunk_chars: int) -> int:
        self.remove(path)
        chunks = split(messages, chunk_chars)
        self._connection.executemany(
            "INSERT INTO raw_chunks(name, path, anchor, text) VALUES(?, ?, ?, ?)",
            [
                (
                    render_pointer(Pointer(session, pointer.start, pointer.end)),
                    path,
                    f"{pointer.start}-{pointer.end}",
                    text,
                )
                for pointer, text in chunks
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


def split(messages: list[Message], chunk_chars: int) -> list[tuple[Pointer, str]]:
    """Consecutive messages packed up to a size; the pointer is the message range."""
    chunks: list[tuple[Pointer, str]] = []
    current: list[Message] = []
    size = 0
    for message in messages:
        if not message.text:
            continue
        if current and size + len(message.text) > chunk_chars:
            chunks.append(_chunk(current))
            current = []
            size = 0
        current.append(message)
        size += len(message.text)
    if current:
        chunks.append(_chunk(current))
    return chunks


def _chunk(messages: list[Message]) -> tuple[Pointer, str]:
    text = PARAGRAPH_BREAK.join(
        f"{message.role}: {message.text}" if message.role else message.text for message in messages
    )
    return Pointer("", messages[0].index, messages[-1].index), text
