"""One memory file = one invalidation atom (Invariant 7). This is its shape and its gate.

A file is active or invalid, nothing in between, and invalidation comes only from
replacement or deletion (ADR-009). The schema-declared fields of a memory ride in the same
frontmatter as the core fields.
"""

from __future__ import annotations

import dataclasses
import pathlib

from . import frontmatter, slug, timestamp
from .config import Config
from .errors import FieldError, ValidationError
from .schema import MemorySchema

STATUS_ACTIVE = "active"
STATUS_INVALID = "invalid"
STATUSES = (STATUS_ACTIVE, STATUS_INVALID)

FIELD_ORDER = (
    "name",
    "abstract",
    "type",
    "status",
    "created",
    "updated",
    "valid_from",
    "invalid_at",
    "superseded_by",
    "weight",
    "author",
    "links",
    "provenance",
)
CORE_FIELDS = frozenset(FIELD_ORDER)
REQUIRED_FIELDS = ("name", "abstract", "type", "created", "updated", "author")
DATE_FIELDS = ("created", "updated", "valid_from", "invalid_at")


@dataclasses.dataclass
class MemoryRecord:
    name: str
    abstract: str
    type: str
    author: str
    created: str
    updated: str
    body: str = ""
    status: str = STATUS_ACTIVE
    valid_from: str | None = None
    invalid_at: str | None = None
    superseded_by: str | None = None
    weight: float = 1.0
    links: list[str] = dataclasses.field(default_factory=list)
    provenance: list[str] = dataclasses.field(default_factory=list)
    fields: dict[str, str] = dataclasses.field(default_factory=dict)
    path: pathlib.Path | None = None

    def frontmatter_fields(self) -> dict[str, object]:
        core: dict[str, object] = {
            "name": self.name,
            "abstract": self.abstract,
            "type": self.type,
            "status": self.status,
            "created": self.created,
            "updated": self.updated,
            "valid_from": self.valid_from or self.created,
            "invalid_at": self.invalid_at,
            "superseded_by": self.superseded_by,
            "weight": float(self.weight),
            "author": self.author,
            "links": list(self.links),
            "provenance": list(self.provenance),
        }
        for key, value in self.fields.items():
            if key not in CORE_FIELDS:
                core[key] = value
        return core

    def to_text(self) -> str:
        return frontmatter.render(self.frontmatter_fields(), self.body)

    def is_active(self) -> bool:
        return self.status == STATUS_ACTIVE

    @classmethod
    def from_text(cls, text: str, path: pathlib.Path | None = None) -> MemoryRecord:
        raw, body = frontmatter.parse(text)
        extra = {
            str(key): str(value)
            for key, value in raw.items()
            if key not in CORE_FIELDS and value is not None and not isinstance(value, list)
        }
        return cls(
            name=str(raw.get("name") or ""),
            abstract=str(raw.get("abstract") or ""),
            type=str(raw.get("type") or ""),
            author=str(raw.get("author") or ""),
            created=str(raw.get("created") or ""),
            updated=str(raw.get("updated") or ""),
            body=body,
            status=str(raw.get("status") or STATUS_ACTIVE),
            valid_from=_optional_str(raw.get("valid_from")),
            invalid_at=_optional_str(raw.get("invalid_at")),
            superseded_by=_optional_str(raw.get("superseded_by")),
            weight=_as_float(raw.get("weight")),
            links=_as_list(raw.get("links")),
            provenance=_as_list(raw.get("provenance")),
            fields=extra,
            path=path,
        )


def validate(record: MemoryRecord, config: Config, schema: MemorySchema | None = None) -> None:
    errors: list[FieldError] = []
    fields = record.frontmatter_fields()

    for field in REQUIRED_FIELDS:
        if not str(fields.get(field) or "").strip():
            errors.append(FieldError(field, "required"))

    if record.name and not slug.is_valid_slug(record.name):
        errors.append(FieldError("name", "must be a kebab-case slug"))
    if len(record.name) > config.storage.slug_max_length:
        errors.append(FieldError("name", "exceeds slug_max_length"))
    if len(record.abstract) > config.storage.abstract_max_chars:
        errors.append(FieldError("abstract", "exceeds abstract_max_chars"))
    if "\n" in record.abstract:
        errors.append(FieldError("abstract", "must be a single line"))
    if record.type and not slug.is_valid_slug(record.type):
        errors.append(FieldError("type", "must be a kebab-case slug"))
    if schema is not None:
        for key_field in schema.key:
            if not str(record.fields.get(key_field) or "").strip():
                errors.append(FieldError(key_field, "required key field"))

    for field in DATE_FIELDS:
        value = fields.get(field)
        if value and not timestamp.is_valid(str(value)):
            errors.append(FieldError(field, "must be an ISO 8601 day or zone-aware instant"))

    if record.status not in STATUSES:
        errors.append(FieldError("status", f"must be one of {', '.join(STATUSES)}"))
    if record.status == STATUS_INVALID and not record.invalid_at:
        errors.append(FieldError("invalid_at", "an invalid record records when it became so"))
    if record.status == STATUS_ACTIVE and (record.invalid_at or record.superseded_by):
        errors.append(FieldError("status", "an active record has no successor and no invalid_at"))
    if record.superseded_by and not slug.is_valid_slug(record.superseded_by):
        errors.append(FieldError("superseded_by", "must be a slug"))
    if record.superseded_by == record.name and record.name:
        errors.append(FieldError("superseded_by", "cannot supersede itself"))
    if not config.weight.floor <= record.weight <= config.weight.ceiling:
        errors.append(FieldError("weight", "outside the configured weight range"))
    for link in record.links:
        if not slug.is_valid_slug(str(link)):
            errors.append(FieldError("links", f"not a slug: {link}"))

    if errors:
        raise ValidationError(errors)


def canonicalise_dates(record: MemoryRecord) -> None:
    for field in DATE_FIELDS:
        value = getattr(record, field)
        if value:
            setattr(record, field, timestamp.canonical(str(value)))


def invalidate(record: MemoryRecord, at: str, successor: str | None = None) -> None:
    """The only way a record leaves the active set: replaced, or deleted."""
    record.status = STATUS_INVALID
    record.invalid_at = at
    record.superseded_by = successor


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_float(value: object) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return Config.default().weight.initial


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []
