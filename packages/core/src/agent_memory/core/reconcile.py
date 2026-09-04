"""The reconcile sheet: what the store already knows, handed to the executor before it writes.

Handles are the only way an operation may name an existing memory, and the sheet is the only
place handles come from. A write that names anything else is rejected before it reaches the
store, so an executor steered by the conversation can at most write a new file.
"""

from __future__ import annotations

import dataclasses
import json

from .config import Config
from .errors import FieldError
from .paths import StoreLayout
from .recall import Recall
from .record import MemoryRecord
from .schema import MemorySchema
from .sessions import Message, Pointer, render_pointer
from .store import Store

OP_NEW = "new"
OP_SUPERSEDE = "supersede"
OP_UPDATE = "update"
OP_SKIP = "skip"
OPS = (OP_NEW, OP_SUPERSEDE, OP_UPDATE, OP_SKIP)
KEY_OP = "op"
KEY_HANDLE = "handle"
KEY_SUPERSEDES = "supersedes"
KEY_PROVENANCE = "provenance"
KEY_TYPE = "type"
FENCE = "```"
TYPE_PROFILE = "profile"
RANGE_SEPARATOR = "-"


@dataclasses.dataclass(frozen=True)
class Handle:
    name: str
    type: str
    status: str
    valid_from: str
    abstract: str

    def render(self) -> str:
        return f"- {self.name} [{self.type}, since {self.valid_from}]: {self.abstract}"


@dataclasses.dataclass(frozen=True)
class Sheet:
    session: str
    pointer: Pointer
    handles: tuple[Handle, ...]
    menus: dict[str, tuple[str, ...]]
    profile: tuple[str, ...]
    slots: tuple[MemorySchema, ...]

    def handle_names(self) -> set[str]:
        return {handle.name for handle in self.handles}

    def render(self) -> str:
        lines = ["## Existing memories this conversation may touch"]
        lines.extend(handle.render() for handle in self.handles)
        if not self.handles:
            lines.append("- (none found)")
        lines.append("")
        lines.append("## Existing groups, per type")
        for type_name, groups in sorted(self.menus.items()):
            lines.append(f"- {type_name}: {', '.join(groups) if groups else '(none yet)'}")
        lines.append("")
        lines.append("## Who this is about")
        lines.extend(f"- {line}" for line in self.profile)
        if not self.profile:
            lines.append("- (no profile yet)")
        return "\n".join(lines)


def build(store: Store, session: str, messages: list[Message]) -> Sheet:
    config: Config = store.config
    text = " ".join(message.text for message in messages)[: config.write.reconcile_query_chars]
    hits = (
        Recall(store).recall(text, limit=config.write.reconcile_entries, log=False) if text else []
    )
    handles = tuple(
        Handle(hit.name, hit.type, hit.status, hit.updated, hit.abstract) for hit in hits
    )
    layout: StoreLayout = store.layout
    schemas = tuple(store.schemas.all())
    menus = {
        schema.type: tuple(sorted(layout.groups_of(schema.type)))
        for schema in schemas
        if schema.group
    }
    profile = tuple(record.abstract for record in store.records() if record.type == TYPE_PROFILE)
    first = messages[0].index if messages else 0
    last = messages[-1].index if messages else first
    return Sheet(session, Pointer(session, first, last), handles, menus, profile, schemas)


def parse_operations(reply: str) -> tuple[list[dict[str, object]], list[FieldError]]:
    """One JSON object per line. A line that is not one is reported, never guessed at."""
    specs: list[dict[str, object]] = []
    errors: list[FieldError] = []
    for number, line in enumerate(reply.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith(FENCE):
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            errors.append(FieldError(f"line {number}", "not a JSON object"))
            continue
        if not isinstance(payload, dict):
            errors.append(FieldError(f"line {number}", "not a JSON object"))
            continue
        specs.append(payload)
    return specs, errors


def check(spec: dict[str, object], sheet: Sheet) -> list[FieldError]:
    """Handles must come from the sheet; provenance defaults to the batch it came from."""
    errors: list[FieldError] = []
    op = str(spec.get(KEY_OP) or OP_NEW)
    if op not in OPS:
        errors.append(FieldError(KEY_OP, f"must be one of {', '.join(OPS)}"))
        return errors
    handle = str(spec.get(KEY_HANDLE) or spec.get(KEY_SUPERSEDES) or "")
    if op in (OP_SUPERSEDE, OP_UPDATE):
        if not handle:
            errors.append(FieldError(KEY_HANDLE, f"{op} names an existing memory"))
        elif handle not in sheet.handle_names():
            errors.append(FieldError(KEY_HANDLE, f"{handle} is not on the reconcile sheet"))
    if op == OP_NEW and handle and handle in sheet.handle_names():
        errors.append(FieldError(KEY_HANDLE, f"{handle} exists; use update or supersede"))
    return errors


def to_record_spec(spec: dict[str, object], sheet: Sheet) -> dict[str, object] | None:
    """The executor's operation, as the store's single write path takes it. Skip is nothing."""
    op = str(spec.get(KEY_OP) or OP_NEW)
    if op == OP_SKIP:
        return None
    handle = str(spec.get(KEY_HANDLE) or spec.get(KEY_SUPERSEDES) or "")
    record_spec = {key: value for key, value in spec.items() if key not in (KEY_OP, KEY_HANDLE)}
    if op == OP_SUPERSEDE:
        record_spec[KEY_SUPERSEDES] = handle
    elif op == OP_UPDATE:
        record_spec["name"] = handle
        record_spec.pop(KEY_SUPERSEDES, None)
    else:
        record_spec.pop(KEY_SUPERSEDES, None)
    record_spec[KEY_PROVENANCE] = _provenance(spec.get(KEY_PROVENANCE), sheet)
    return record_spec


def _provenance(raw: object, sheet: Sheet) -> list[str]:
    items = raw if isinstance(raw, list) else ([raw] if raw else [])
    pointers: list[str] = []
    for item in items:
        text = str(item).strip()
        if not text:
            continue
        start, separator, end = text.partition(RANGE_SEPARATOR)
        if start.isdigit() and (end.isdigit() or not separator):
            pointers.append(
                render_pointer(
                    Pointer(sheet.session, int(start), int(end) if end.isdigit() else int(start))
                )
            )
        else:
            pointers.append(text)
    return pointers or [render_pointer(sheet.pointer)]


def profile_lines(records: list[MemoryRecord]) -> tuple[str, ...]:
    return tuple(record.abstract for record in records if record.type == TYPE_PROFILE)
