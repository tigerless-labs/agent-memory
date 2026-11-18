"""BM25 over abstract + body (ADR-003). Projection only: never a source of truth."""

from __future__ import annotations

import dataclasses
import sqlite3

from .chunking import Chunk
from .database import SURFACE_ACTIVE, SURFACE_HISTORY
from .record import MemoryRecord
from .tokenization import (
    TOKENIZER_ASCII,
    query_tokens,
    segment_text,
    validate_tokenizer,
)

LINK_SEPARATOR = ","
SURFACES = (SURFACE_ACTIVE, SURFACE_HISTORY)
FIELDS_PROJECTION_KEY = "fields_projection"


@dataclasses.dataclass(frozen=True)
class Candidate:
    name: str
    kind: str
    anchor: str
    heading: str
    relevance: float


def to_match_query(query: str, tokenizer: str = TOKENIZER_ASCII) -> str:
    tokens = query_tokens(query, tokenizer)
    return " OR ".join(f'"{token}"' for token in dict.fromkeys(tokens))


class SearchIndex:
    def __init__(self, connection: sqlite3.Connection, tokenizer: str = TOKENIZER_ASCII):
        validate_tokenizer(tokenizer)
        self._connection = connection
        self._tokenizer = tokenizer

    def upsert(self, record: MemoryRecord, chunks: list[Chunk], relative_path: str) -> None:
        self.remove(record.name)
        self._connection.execute(
            "INSERT INTO records(name, path, type, abstract, created, updated, "
            "valid_from, invalid_at, superseded_by, weight, author, links, provenance) "
            "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record.name,
                relative_path,
                record.type,
                record.abstract,
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
        self._connection.executemany(
            "INSERT INTO record_fields(name, key, value) VALUES(?, ?, ?)",
            [(record.name, key, value) for key, value in record.fields.items()],
        )
        surface = SURFACE_ACTIVE if record.is_active() else SURFACE_HISTORY
        self._connection.executemany(
            f"INSERT INTO {surface}(name, kind, anchor, heading, text) VALUES(?, ?, ?, ?, ?)",
            [
                (
                    record.name,
                    chunk.kind,
                    chunk.anchor,
                    chunk.heading,
                    segment_text(chunk.text, self._tokenizer),
                )
                for chunk in chunks
            ],
        )

    def remove(self, name: str) -> None:
        self._connection.execute("DELETE FROM record_fields WHERE name = ?", (name,))
        self._connection.execute("DELETE FROM records WHERE name = ?", (name,))
        for surface in SURFACES:
            self._connection.execute(f"DELETE FROM {surface} WHERE name = ?", (name,))

    def remove_path(self, path: str) -> None:
        rows = self._connection.execute(
            "SELECT name FROM records WHERE path = ?", (path,)
        ).fetchall()
        for row in rows:
            self.remove(row["name"])

    def fields_ready(self) -> bool:
        return self._connection.execute(
            "SELECT 1 FROM index_meta WHERE key = ?", (FIELDS_PROJECTION_KEY,)
        ).fetchone() is not None

    def mark_fields_ready(self) -> None:
        self._connection.execute(
            "INSERT OR REPLACE INTO index_meta(key, value) VALUES(?, ?)",
            (FIELDS_PROJECTION_KEY, "1"),
        )

    def rows(
        self, include_invalid: bool = True, *, fields: dict[str, str] | None = None
    ) -> list[sqlite3.Row]:
        conditions, parameters = field_conditions(fields)
        if not include_invalid:
            conditions.append("invalid_at IS NULL")
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        return self._connection.execute("SELECT * FROM records" + where, parameters).fetchall()

    def row(self, name: str) -> sqlite3.Row | None:
        return self._connection.execute("SELECT * FROM records WHERE name = ?", (name,)).fetchone()

    def match(
        self,
        query: str,
        pool: int,
        surface: str = SURFACE_ACTIVE,
        *,
        scope_path: str | None = None,
        fields: dict[str, str] | None = None,
    ) -> list[Candidate]:
        if surface not in SURFACES:
            raise ValueError(f"unknown surface {surface}")
        expression = to_match_query(query, self._tokenizer)
        if not expression or scope_path == "":
            return []
        conditions, field_parameters = field_conditions(fields)
        parameters: list[object] = [expression, *field_parameters]
        if scope_path is not None:
            prefix = scope_path + "/"
            conditions.append("(records.path = ? OR substr(records.path, 1, ?) = ?)")
            parameters.extend((scope_path, len(prefix), prefix))
        join = f" JOIN records ON records.name = {surface}.name" if conditions else ""
        where = " AND " + " AND ".join(conditions) if conditions else ""
        statement = (
            f"SELECT {surface}.name, kind, anchor, heading, bm25({surface}) AS rank "
            f"FROM {surface}{join} WHERE {surface} MATCH ?{where} ORDER BY rank LIMIT ?"
        )
        parameters.append(pool)
        rows = self._connection.execute(statement, parameters).fetchall()
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


def field_conditions(fields: dict[str, str] | None) -> tuple[list[str], list[object]]:
    conditions = []
    parameters: list[object] = []
    for key, value in (fields or {}).items():
        conditions.append(
            "EXISTS (SELECT 1 FROM record_fields WHERE record_fields.name = records.name "
            "AND record_fields.key = ? AND record_fields.value = ?)"
        )
        parameters.extend((key, value))
    return conditions, parameters
