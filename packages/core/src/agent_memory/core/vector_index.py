"""Small, rebuildable dense projection using SQLite storage and brute-force cosine."""

from __future__ import annotations

import array
import math
import sqlite3

from .chunking import Chunk
from .embeddings import Embedder
from .record import MemoryRecord
from .search_index import Candidate


def _pack(values: list[float]) -> bytes:
    return array.array("f", values).tobytes()


def _unpack(value: bytes) -> list[float]:
    result = array.array("f")
    result.frombytes(value)
    return result.tolist()


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        return -1.0
    denominator = math.sqrt(sum(x * x for x in left)) * math.sqrt(sum(x * x for x in right))
    if not denominator:
        return 0.0
    return sum(x * y for x, y in zip(left, right, strict=True)) / denominator


class VectorIndex:
    def __init__(self, connection: sqlite3.Connection, embedder: Embedder, model: str):
        self._connection = connection
        self._embedder = embedder
        self._model = model

    def known(self) -> dict[str, tuple[str, str]]:
        rows = self._connection.execute(
            "SELECT path, content_hash, model FROM vector_files"
        ).fetchall()
        return {str(row["path"]): (str(row["content_hash"]), str(row["model"])) for row in rows}

    def upsert(
        self, path: str, digest: str, record: MemoryRecord, chunks: list[Chunk]
    ) -> None:
        embeddings = self._embedder.embed_documents([chunk.text for chunk in chunks])
        if len(embeddings) != len(chunks):
            raise ValueError("embedding backend returned an unexpected number of vectors")
        self.remove_path(path)
        self._connection.execute(
            "INSERT INTO vector_files(path, content_hash, model) VALUES(?, ?, ?)",
            (path, digest, self._model),
        )
        self._connection.executemany(
            "INSERT INTO vector_chunks(path, chunk_index, name, kind, anchor, heading, embedding) "
            "VALUES(?, ?, ?, ?, ?, ?, ?)",
            [
                (path, index, record.name, chunk.kind, chunk.anchor, chunk.heading, _pack(vector))
                for index, (chunk, vector) in enumerate(zip(chunks, embeddings, strict=True))
            ],
        )

    def remove(self, name: str) -> None:
        paths = self._connection.execute(
            "SELECT DISTINCT path FROM vector_chunks WHERE name = ?", (name,)
        ).fetchall()
        for row in paths:
            self.remove_path(str(row["path"]))

    def remove_path(self, path: str) -> None:
        self._connection.execute("DELETE FROM vector_chunks WHERE path = ?", (path,))
        self._connection.execute("DELETE FROM vector_files WHERE path = ?", (path,))

    def match(self, query: str, pool: int) -> list[Candidate]:
        query_vector = self._embedder.embed_query(query)
        rows = self._connection.execute(
            "SELECT name, kind, anchor, heading, embedding FROM vector_chunks"
        ).fetchall()
        candidates = [
            Candidate(
                name=str(row["name"]),
                kind=str(row["kind"]),
                anchor=str(row["anchor"]),
                heading=str(row["heading"]),
                relevance=_cosine(query_vector, _unpack(row["embedding"])),
            )
            for row in rows
        ]
        candidates.sort(
            key=lambda item: (-item.relevance, item.name, item.kind, item.anchor, item.heading)
        )
        return candidates[:pool]
