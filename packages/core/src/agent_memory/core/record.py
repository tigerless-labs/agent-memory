"""One memory file = one validity interval. Old files remain available for history."""

from __future__ import annotations

import dataclasses
import hashlib
import pathlib

from . import frontmatter, slug, timestamp
from .config import Config
from .errors import FieldError, ValidationError
from .schema import MemorySchema

STATUS_ACTIVE = "active"
STATUS_INVALID = "invalid"

FIELD_ORDER = (
    "name",
    "abstract",
    "type",
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
CORE_FIELDS = frozenset(FIELD_ORDER) | {"status"}
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
    valid_from: str | None = None
    invalid_at: str | None = None
    superseded_by: str | None = None
    weight: float = 1.0
    links: list[str] = dataclasses.field(default_factory=list)
    provenance: list[str] = dataclasses.field(default_factory=list)
    fields: dict[str, str] = dataclasses.field(default_factory=dict)
    path: pathlib.Path | None = None
    source_hash: str | None = dataclasses.field(default=None, repr=False, compare=False)

    def frontmatter_fields(self) -> dict[str, object]:
        core: dict[str, object] = {
            "name": self.name,
            "abstract": self.abstract,
            "type": self.type,
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
        return self.invalid_at is None

    @property
    def status(self) -> str:
        """Compatibility view for callers; the interval is the sole stored state."""
        return STATUS_ACTIVE if self.is_active() else STATUS_INVALID

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
            valid_from=_optional_str(raw.get("valid_from")),
            invalid_at=_optional_str(raw.get("invalid_at"))
            or (
                _optional_str(raw.get("updated"))
                if raw.get("status") in (STATUS_INVALID, "retired")
                else None
            ),
            superseded_by=_optional_str(raw.get("superseded_by")),
            weight=_as_float(raw.get("weight")),
            links=_as_list(raw.get("links")),
            provenance=_as_list(raw.get("provenance")),
            fields=extra,
            path=path,
            source_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
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

    start = record.valid_from or record.created
    if (
        record.invalid_at
        and timestamp.is_valid(start)
        and timestamp.is_valid(record.invalid_at)
        and timestamp.parse(record.invalid_at) < timestamp.parse(start)
    ):
        errors.append(FieldError("invalid_at", "must not precede valid_from"))

    if record.superseded_by and not record.invalid_at:
        errors.append(FieldError("invalid_at", "a successor requires an ended validity interval"))
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
    start = timestamp.parse(record.valid_from or record.created)
    end = timestamp.parse(at)
    record.invalid_at = timestamp.canonical(max(start, end).isoformat())
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
