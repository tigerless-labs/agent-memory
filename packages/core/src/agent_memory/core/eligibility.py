"""Shared Read eligibility; preserve Recall's lifecycle and path-prefix semantics."""

from __future__ import annotations

from typing import Any, Protocol

from . import timestamp


class MetadataRow(Protocol):
    def __getitem__(self, key: str) -> Any: ...


def eligible[Row: MetadataRow](
    rows: list[Row],
    scope: str | None,
    as_of: str | None,
    deep: bool,
) -> dict[str, Row]:
    allowed: dict[str, Row] = {}
    moment = timestamp.parse(as_of) if as_of else None
    for row in rows:
        if moment is None and (int(row["archived"]) or row["invalid_at"]):
            continue
        if scope and not _in_scope(str(row["path"]), scope):
            continue
        if moment is not None:
            if timestamp.parse(str(row["valid_from"])) > moment:
                continue
            ended = row["invalid_at"]
            if ended and timestamp.parse(str(ended)) <= moment:
                continue
        allowed[str(row["name"])] = row
    return allowed


def _in_scope(path: str, scope: str) -> bool:
    return path.startswith(scope.strip("/"))
