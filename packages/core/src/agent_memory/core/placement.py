"""Where a memory lives is a function of its type and its key, never a choice the writer makes.

The convention is fixed: type / group / key. A directory segment only ever comes from a
system-supplied value or from a menu of directories that already exist, so two writers
describing the same thing land in the same place (ADR-008).
"""

from __future__ import annotations

import dataclasses
import hashlib
import pathlib

from . import timestamp
from .config import Config
from .errors import FieldError, ValidationError
from .paths import MEMORY_SUFFIX
from .schema import SOURCE_FIELD, SOURCE_MENU, SOURCE_SYSTEM, MemorySchema, source_of
from .slug import slugify

FIELD_PROJECT = "project"
FIELD_USER = "user"
FIELD_DATE = "date"
DATE_GROUP_FORMAT = "%Y-%m"
SEGMENT_SEPARATOR = "-"
RESERVED_SEGMENT_SUFFIX = "-x"
TRUNCATION_HASH_LENGTH = 8
TRUNCATION_PROBE_FACTOR = 2
WINDOWS_RESERVED_STEMS = frozenset(
    {"con", "prn", "aux", "nul"}
    | {f"com{index}" for index in range(1, 10)}
    | {f"lpt{index}" for index in range(1, 10)}
)


@dataclasses.dataclass(frozen=True)
class Placement:
    relative_path: pathlib.Path
    name: str
    group: str | None
    fields: dict[str, str]


def system_default(field: str, config: Config, valid_from: str | None, now: str) -> str | None:
    if field == FIELD_PROJECT:
        return config.storage.default_project
    if field == FIELD_USER:
        return config.storage.default_user
    if field == FIELD_DATE:
        return timestamp.parse(valid_from or now).strftime(DATE_GROUP_FORMAT)
    return None


def portable_segment(text: str, config: Config) -> str:
    limit = config.storage.slug_max_length
    slug = slugify(text, limit)
    if len(slugify(text, limit * TRUNCATION_PROBE_FACTOR)) > limit:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:TRUNCATION_HASH_LENGTH]
        slug = slug[: limit - TRUNCATION_HASH_LENGTH - 1].rstrip("-") + "-" + digest
    if slug in WINDOWS_RESERVED_STEMS:
        slug += RESERVED_SEGMENT_SUFFIX
    return slug


def resolve(
    schema: MemorySchema,
    fields: dict[str, object],
    config: Config,
    existing_groups: set[str],
    *,
    valid_from: str | None,
    now: str,
    name: str | None = None,
    create_group: bool = False,
    fallback: str | None = None,
) -> Placement:
    errors: list[FieldError] = []
    settled: dict[str, str] = {
        str(key): str(value).strip() for key, value in fields.items() if str(value).strip()
    }
    for field in schema.key:
        if settled.get(field):
            continue
        source = source_of(field, config)
        if source == SOURCE_SYSTEM:
            default = system_default(field, config, valid_from, now)
            if default:
                settled[field] = default
                continue
        if source == SOURCE_MENU:
            settled[field] = config.storage.default_group
            continue
        if name or fallback:
            settled[field] = str(name or fallback)
            continue
        errors.append(FieldError(field, "required key field"))
    if errors:
        raise ValidationError(errors)

    group: str | None = None
    if schema.group:
        raw_group = settled[schema.group]
        group = portable_segment(raw_group, config)
        if not group:
            raise ValidationError([FieldError(schema.group, "empty after slugging")])
        source = source_of(schema.group, config)
        if source == SOURCE_MENU and not (
            group in existing_groups or group == config.storage.default_group or create_group
        ):
            menu = ", ".join(sorted(existing_groups)) or "(none yet)"
            raise ValidationError(
                [
                    FieldError(
                        schema.group,
                        f"{group} is not an existing {schema.type} group; menu: {menu};"
                        " pass create_group to add it",
                    )
                ]
            )
        if source == SOURCE_FIELD:
            raise ValidationError([FieldError(schema.group, "free fields cannot name a directory")])
        settled[schema.group] = group

    stem = name or portable_segment(
        SEGMENT_SEPARATOR.join(settled[field] for field in schema.key_without_group), config
    )
    if not stem:
        raise ValidationError([FieldError("name", "key fields produce an empty name")])
    parts = [schema.type] + ([group] if group else []) + [stem + MEMORY_SUFFIX]
    if len(parts) > config.storage.max_depth:
        raise ValidationError([FieldError("path", "exceeds max_depth")])
    return Placement(pathlib.Path(*parts), stem, group, settled)
