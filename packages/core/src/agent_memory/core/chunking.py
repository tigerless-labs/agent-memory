"""Splitting exists only to give the index a surface. The recall unit stays the whole file."""

from __future__ import annotations

import dataclasses

from .config import Config
from .record import MemoryRecord
from .slug import slugify

KIND_ABSTRACT = "abstract"
KIND_BODY = "body"
HEADING_PREFIX = "#"


@dataclasses.dataclass(frozen=True)
class Chunk:
    kind: str
    heading: str
    anchor: str
    text: str


@dataclasses.dataclass(frozen=True)
class OutlineEntry:
    level: int
    title: str
    anchor: str


def outline(body: str, config: Config) -> list[OutlineEntry]:
    entries: list[OutlineEntry] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped.startswith(HEADING_PREFIX):
            continue
        marker, _, title = stripped.partition(" ")
        if set(marker) != {HEADING_PREFIX} or not title.strip():
            continue
        entries.append(
            OutlineEntry(
                level=len(marker),
                title=title.strip(),
                anchor=slugify(title, config.storage.slug_max_length),
            )
        )
    return entries


def chunks(record: MemoryRecord, config: Config) -> list[Chunk]:
    result = [Chunk(KIND_ABSTRACT, record.name, "", record.abstract)]
    body = record.body.strip()
    if not body:
        return result
    sections = _sections(body) if len(body) >= config.index.chunk_min_chars else []
    if not sections:
        result.append(Chunk(KIND_BODY, "", "", body))
        return result
    for heading, text in sections:
        anchor = slugify(heading, config.storage.slug_max_length) if heading else ""
        result.append(Chunk(KIND_BODY, heading, anchor, text.strip()))
    return result


def _sections(body: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, list[str]]] = []
    current_heading = ""
    current: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        marker, _, title = stripped.partition(" ")
        is_heading = stripped.startswith(HEADING_PREFIX) and set(marker) == {HEADING_PREFIX}
        if is_heading and title.strip():
            if current_heading or "".join(current).strip():
                sections.append((current_heading, current))
            current_heading = title.strip()
            current = []
        else:
            current.append(line)
    if current_heading or "".join(current).strip():
        sections.append((current_heading, current))
    collapsed = [(heading, "\n".join(lines)) for heading, lines in sections]
    return [item for item in collapsed if item[0] or item[1].strip()]
