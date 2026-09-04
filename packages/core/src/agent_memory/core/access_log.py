"""Usage telemetry, written on read. The only thing a read is allowed to write (Invariant 3)."""

from __future__ import annotations

import dataclasses
import datetime as dt
import sqlite3

KIND_RECALL = "recall"
KIND_READ = "read"


@dataclasses.dataclass(frozen=True)
class AccessEntry:
    at: str
    name: str
    query: str
    kind: str
    agent: str


class AccessLog:
    def __init__(self, connection: sqlite3.Connection):
        self._connection = connection

    def append(self, entries: list[AccessEntry]) -> None:
        self._connection.executemany(
            "INSERT INTO access_log(at, name, query, kind, agent) VALUES(?, ?, ?, ?, ?)",
            [(entry.at, entry.name, entry.query, entry.kind, entry.agent) for entry in entries],
        )

    def entries(self) -> list[sqlite3.Row]:
        return self._connection.execute("SELECT * FROM access_log ORDER BY at").fetchall()

    def cursor(self) -> int:
        row = self._connection.execute(
            "SELECT COALESCE(MAX(rowid), 0) AS cursor FROM access_log"
        ).fetchone()
        return int(row["cursor"])

    def entries_after(self, cursor: int) -> list[sqlite3.Row]:
        return self._connection.execute(
            "SELECT * FROM access_log WHERE rowid > ? ORDER BY rowid", (cursor,)
        ).fetchall()

    def counts(self, since: dt.datetime | None = None) -> dict[str, int]:
        if since is None:
            rows = self._connection.execute(
                "SELECT name, COUNT(*) AS hits FROM access_log GROUP BY name"
            ).fetchall()
        else:
            rows = self._connection.execute(
                "SELECT name, COUNT(*) AS hits FROM access_log WHERE at >= ? GROUP BY name",
                (since.isoformat(),),
            ).fetchall()
        return {row["name"]: int(row["hits"]) for row in rows}

    def last_access(self) -> dict[str, str]:
        rows = self._connection.execute(
            "SELECT name, MAX(at) AS last FROM access_log GROUP BY name"
        ).fetchall()
        return {row["name"]: str(row["last"]) for row in rows}
