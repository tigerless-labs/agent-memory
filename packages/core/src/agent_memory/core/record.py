"""One memory file = one invalidation atom (Invariant 7). This is its shape and its gate."""

from __future__ import annotations

import dataclasses
import pathlib

from . import frontmatter, slug, timestamp
from .config import Config
from .errors import FieldError, ValidationError

STATUS_ACTIVE = "active"
STATUS_STALE = "stale"
STATUS_RETIRED = "retired"
STATUSES = (STATUS_ACTIVE, STATUS_STALE, STATUS_RETIRED)

FIELD_ORDER = (
    "name",
    "abstract",
    "type",
    "status",
    "created",
    "updated",
    "valid_from",
    "superseded_by",
    "weight",
    "author",
    "links",
    "provenance",
)
REQUIRED_FIELDS = ("name", "abstract", "type", "created", "updated", "author")
DATE_FIELDS = ("created", "updated", "valid_from")


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
    superseded_by: str | None = None
    weight: float = 1.0
    links: list[str] = dataclasses.field(default_factory=list)
    provenance: list[str] = dataclasses.field(default_factory=list)
    domain: str = ""
    path: pathlib.Path | None = None

    def frontmatter_fields(self) -> dict[str, object]:
        return {
            "name": self.name,
            "abstract": self.abstract,
            "type": self.type,
            "status": self.status,
            "created": self.created,
            "updated": self.updated,
            "valid_from": self.valid_from or self.created,
            "superseded_by": self.superseded_by,
            "weight": float(self.weight),
            "author": self.author,
            "links": list(self.links),
            "provenance": list(self.provenance),
        }

    def to_text(self) -> str:
        return frontmatter.render(self.frontmatter_fields(), self.body)

    def is_active(self) -> bool:
        return self.status != STATUS_RETIRED and not self.superseded_by

    @classmethod
    def from_text(cls, text: str, domain: str, path: pathlib.Path | None = None) -> MemoryRecord:
        fields, body = frontmatter.parse(text)
        return cls(
            name=str(fields.get("name") or ""),
            abstract=str(fields.get("abstract") or ""),
            type=str(fields.get("type") or ""),
            author=str(fields.get("author") or ""),
            created=str(fields.get("created") or ""),
            updated=str(fields.get("updated") or ""),
            body=body,
            status=str(fields.get("status") or STATUS_ACTIVE),
            valid_from=_optional_str(fields.get("valid_from")),
            superseded_by=_optional_str(fields.get("superseded_by")),
            weight=_as_float(fields.get("weight")),
            links=_as_list(fields.get("links")),
            provenance=_as_list(fields.get("provenance")),
            domain=domain,
            path=path,
        )


def validate(record: MemoryRecord, config: Config) -> None:
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

    if record.domain not in config.storage.domains:
        errors.append(FieldError("domain", f"unknown domain: {record.domain}"))
    elif record.type and record.type not in config.storage.domain_types[record.domain]:
        allowed = ", ".join(config.storage.domain_types[record.domain])
        errors.append(
            FieldError(
                "type",
                f"domain {record.domain} takes one of: {allowed} (got {record.type})",
            )
        )

    for field in DATE_FIELDS:
        value = fields.get(field)
        if value and not timestamp.is_valid(str(value)):
            errors.append(FieldError(field, "must be an ISO 8601 day or zone-aware instant"))

    if record.status not in STATUSES:
        errors.append(FieldError("status", f"must be one of {', '.join(STATUSES)}"))
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
