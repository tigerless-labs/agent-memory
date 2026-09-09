"""Raw material as numbered messages, and the pointers that reach into it.

A session file is one message per line, each carrying its index and time. Chunking for the
index is a projection over these lines; a pointer names messages, never chunks, so it stays
valid however the index is cut (Invariant 4, ADR-008).
"""

from __future__ import annotations

import dataclasses
import json
import pathlib
import re

from .clock import Clock
from .errors import FieldError, NotFoundError, ValidationError
from .paths import ARCHIVE_DIRNAME, SESSIONS_DIRNAME, StoreLayout

SESSION_SUFFIX = ".jsonl"
ASCII_SPACE = 32
ASCII_DELETE = 127
POINTER_SEPARATOR = "#"
RANGE_SEPARATOR = "-"
ROLE_SEPARATOR = ": "
KNOWN_ROLES = frozenset({"user", "assistant", "system", "tool", "human", "ai"})
KEY_INDEX = "index"
KEY_ROLE = "role"
KEY_TEXT = "text"
KEY_AT = "at"
_POINTER = re.compile(
    rf"^{SESSIONS_DIRNAME}/(?P<session>[^#/]+){POINTER_SEPARATOR}"
    rf"(?P<start>[0-9]+)(?:{RANGE_SEPARATOR}(?P<end>[0-9]+))?$"
)


@dataclasses.dataclass(frozen=True)
class Message:
    index: int
    role: str
    text: str
    at: str

    def as_dict(self) -> dict[str, object]:
        return {KEY_INDEX: self.index, KEY_ROLE: self.role, KEY_TEXT: self.text, KEY_AT: self.at}


@dataclasses.dataclass(frozen=True)
class Pointer:
    session: str
    start: int
    end: int

    def overlaps(self, other: Pointer) -> bool:
        return self.session == other.session and self.start <= other.end and other.start <= self.end


def render_pointer(pointer: Pointer) -> str:
    return (
        f"{SESSIONS_DIRNAME}/{pointer.session}{POINTER_SEPARATOR}"
        f"{pointer.start}{RANGE_SEPARATOR}{pointer.end}"
    )


def parse_pointer(text: str) -> Pointer | None:
    match = _POINTER.fullmatch(str(text).strip())
    if match is None:
        return None
    try:
        start = int(match.group("start"))
        end = int(match.group("end") or start)
    except ValueError:
        return None
    if end < start or not _safe_session(match.group("session")):
        return None
    return Pointer(match.group("session"), start, end)


def _safe_session(session: str) -> bool:
    return (
        bool(session)
        and session not in (".", "..")
        and not any(
            char in "/\\#" or ord(char) < ASCII_SPACE or ord(char) == ASCII_DELETE
            for char in session
        )
    )


def session_path(layout: StoreLayout, session: str) -> pathlib.Path:
    if not _safe_session(session):
        raise ValidationError([FieldError("pointer", "invalid session identifier")])
    path = layout.sessions / f"{session}{SESSION_SUFFIX}"
    # Neither the sessions directory nor the file may redirect outside this store.
    expected = layout.root.resolve() / ARCHIVE_DIRNAME / SESSIONS_DIRNAME / path.name
    if path.resolve() != expected:
        raise ValidationError([FieldError("pointer", "session path redirects the reference")])
    return path


def session_name(path: pathlib.Path) -> str:
    return path.stem


def split_role(line: str) -> tuple[str, str]:
    head, separator, tail = line.partition(ROLE_SEPARATOR)
    if separator and head.strip().lower() in KNOWN_ROLES:
        return head.strip().lower(), tail.strip()
    return "", line.strip()


def append(
    layout: StoreLayout, session: str, items: list[str] | list[dict[str, object]], clock: Clock
) -> Pointer:
    path = session_path(layout, session)
    path.parent.mkdir(parents=True, exist_ok=True)
    start = count(path)
    stamp = clock.timestamp()
    lines: list[str] = []
    for offset, item in enumerate(items):
        message = _coerce(item, start + offset, stamp)
        if message.text:
            lines.append(json.dumps(message.as_dict(), ensure_ascii=False))
    if not lines:
        return Pointer(session, start, max(start - 1, 0))
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    return Pointer(session, start, start + len(lines) - 1)


def count(path: pathlib.Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def read(layout: StoreLayout, session: str) -> list[Message]:
    return read_file(session_path(layout, session))


def read_file(path: pathlib.Path) -> list[Message]:
    if not path.exists():
        return []
    messages: list[Message] = []
    for position, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            role, text = split_role(line)
            messages.append(Message(position, role, text, ""))
            continue
        messages.append(_coerce(payload, position, ""))
    return messages


def resolve(layout: StoreLayout, pointer: Pointer, *, strict: bool = True) -> list[Message]:
    """Read original message indices; strict reads never return an incomplete range.

    Write's evidence-date check explicitly keeps its legacy best-effort behavior.
    """
    if pointer.start < 0 or pointer.end < pointer.start:
        raise ValidationError([FieldError("pointer", "invalid message range")])
    path = session_path(layout, pointer.session)
    if strict and not path.is_file():
        raise NotFoundError(f"no raw session {pointer.session}")
    try:
        messages = [
            message for message in read_file(path) if pointer.start <= message.index <= pointer.end
        ]
    except (OSError, ValueError) as error:
        raise ValidationError([FieldError("pointer", "raw session is unreadable")]) from error
    if strict and (
        len(messages) != pointer.end - pointer.start + 1
        or any(message.index != pointer.start + offset for offset, message in enumerate(messages))
    ):
        raise ValidationError([FieldError("pointer", "message range is missing or inconsistent")])
    return messages


def _coerce(item: object, index: int, stamp: str) -> Message:
    if isinstance(item, dict):
        return Message(
            index=int(item.get(KEY_INDEX, index)),
            role=str(item.get(KEY_ROLE) or ""),
            text=str(item.get(KEY_TEXT) or "").strip(),
            at=str(item.get(KEY_AT) or stamp),
        )
    role, text = split_role(str(item))
    return Message(index=index, role=role, text=text, at=stamp)
