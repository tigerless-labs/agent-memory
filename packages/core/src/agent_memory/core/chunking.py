"""Splitting exists only to give the index a surface. The recall unit stays the whole file."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator

from .config import Config
from .record import MemoryRecord
from .slug import slugify

KIND_ABSTRACT = "abstract"
KIND_BODY = "body"
HEADING_PREFIX = "#"
FENCE_MARKERS = ("```", "~~~")


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


def _fence(stripped: str) -> tuple[str, int] | None:
    """The character and run length a line opens or closes a fenced block with."""
    for marker in FENCE_MARKERS:
        if stripped.startswith(marker):
            char = marker[0]
            return char, len(stripped) - len(stripped.lstrip(char))
    return None


def _heading(stripped: str) -> tuple[int, str] | None:
    marker, _, title = stripped.partition(" ")
    if not stripped.startswith(HEADING_PREFIX) or set(marker) != {HEADING_PREFIX}:
        return None
    cleaned = title.strip()
    return (len(marker), cleaned) if cleaned else None


def _scan(body: str) -> Iterator[tuple[str, tuple[int, str] | None]]:
    """Each line with its heading, or None inside a fenced block.

    A `#` line inside a fence is shell or Python syntax — promoting it to a heading invents a
    section in the outline and cuts the real one in two. A fence closes only on its own
    character, at least as long as the one that opened it, with nothing after it.
    """
    fence: tuple[str, int] | None = None
    for line in body.splitlines():
        stripped = line.strip()
        marker = _fence(stripped)
        if marker is not None:
            char, run = marker
            if fence is None:
                fence = (char, run)
            elif char == fence[0] and run >= fence[1] and not stripped[run:].strip():
                fence = None
            yield line, None
            continue
        yield line, None if fence is not None else _heading(stripped)


def outline(body: str, config: Config) -> list[OutlineEntry]:
    entries: list[OutlineEntry] = []
    for _, heading in _scan(body):
        if heading is None:
            continue
        level, title = heading
        entries.append(
            OutlineEntry(
                level=level,
                title=title,
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
    for line, heading in _scan(body):
        if heading is not None:
            if current_heading or "".join(current).strip():
                sections.append((current_heading, current))
            current_heading = heading[1]
            current = []
        else:
            current.append(line)
    if current_heading or "".join(current).strip():
        sections.append((current_heading, current))
    collapsed = [(heading, "\n".join(lines)) for heading, lines in sections]
    return [item for item in collapsed if item[0] or item[1].strip()]
