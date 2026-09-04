"""The index database. Every table here is a cache — deleting the file loses no knowledge."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from .paths import StoreLayout

SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS files (
        path TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        indexed_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS records (
        name TEXT PRIMARY KEY,
        path TEXT NOT NULL,
        domain TEXT NOT NULL,
        type TEXT NOT NULL,
        abstract TEXT NOT NULL,
        status TEXT NOT NULL,
        created TEXT NOT NULL,
        updated TEXT NOT NULL,
        valid_from TEXT NOT NULL,
        superseded_by TEXT,
        weight REAL NOT NULL,
        author TEXT NOT NULL,
        links TEXT NOT NULL,
        archived INTEGER NOT NULL
    )
    """,
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(
        name UNINDEXED,
        kind UNINDEXED,
        anchor UNINDEXED,
        heading,
        text
    )
    """,
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS raw_chunks USING fts5(
        name UNINDEXED,
        path UNINDEXED,
        anchor UNINDEXED,
        text
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS vector_files (
        path TEXT PRIMARY KEY,
        content_hash TEXT NOT NULL,
        model TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS vector_chunks (
        path TEXT NOT NULL,
        chunk_index INTEGER NOT NULL,
        name TEXT NOT NULL,
        kind TEXT NOT NULL,
        anchor TEXT NOT NULL,
        heading TEXT NOT NULL,
        embedding BLOB NOT NULL,
        PRIMARY KEY(path, chunk_index)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS access_log (
        at TEXT NOT NULL,
        name TEXT NOT NULL,
        query TEXT NOT NULL,
        kind TEXT NOT NULL,
        agent TEXT NOT NULL
    )
    """,
)


class Database:
    def __init__(self, layout: StoreLayout):
        self._layout = layout

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self._layout.index_dir.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._layout.index_db)
        connection.row_factory = sqlite3.Row
        try:
            for statement in SCHEMA:
                connection.execute(statement)
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def drop(self) -> None:
        self._layout.index_db.unlink(missing_ok=True)
