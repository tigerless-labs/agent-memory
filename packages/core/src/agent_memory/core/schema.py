"""A memory type is a small data file. The tree, the slot table and identity all derive from it.

One schema declares four things: what the type is (the slot text an executor reads), which
fields form identity (same key, same file), which field names the subdirectory, and whether a
write may land on an existing file. Everything else about a memory is uniform (ADR-008).
"""

from __future__ import annotations

import dataclasses
import pathlib
import tomllib

from .config import Config
from .errors import FieldError, ValidationError
from .paths import StoreLayout
from .slug import is_valid_slug

SOURCE_SYSTEM = "system"
SOURCE_MENU = "menu"
SOURCE_FIELD = "field"
SOURCES = (SOURCE_SYSTEM, SOURCE_MENU, SOURCE_FIELD)

MODE_UPSERT = "upsert"
MODE_ADD_ONLY = "add_only"
MODES = (MODE_UPSERT, MODE_ADD_ONLY)

SCHEMA_SUFFIX = ".toml"
RESERVED_FIELDS = frozenset(
    {
        "name", "abstract", "type", "status", "created", "updated", "valid_from", "invalid_at",
        "superseded_by", "weight", "author", "links", "provenance", "body", "supersedes",
        "create_group",
    }
)


@dataclasses.dataclass(frozen=True)
class MemorySchema:
    type: str
    description: str
    key: tuple[str, ...]
    group: str | None = None
    mode: str = MODE_UPSERT

    @property
    def key_without_group(self) -> tuple[str, ...]:
        return tuple(field for field in self.key if field != self.group)

    def as_dict(self) -> dict[str, object]:
        return {
            "type": self.type,
            "description": self.description,
            "key": list(self.key),
            "group": self.group,
            "mode": self.mode,
        }


def source_of(field: str, config: Config) -> str:
    return config.storage.field_sources.get(field, SOURCE_FIELD)


def parse(text: str) -> MemorySchema:
    raw = tomllib.loads(text)
    key = raw.get("key", [])
    return MemorySchema(
        type=str(raw.get("type") or ""),
        description=str(raw.get("description") or "").strip(),
        key=tuple(str(item) for item in key) if isinstance(key, list) else (str(key),),
        group=str(raw["group"]) if raw.get("group") else None,
        mode=str(raw.get("mode") or MODE_UPSERT),
    )


def render(schema: MemorySchema) -> str:
    lines = [
        f'type = "{schema.type}"',
        f'description = """{schema.description}"""',
        "key = [" + ", ".join(f'"{field}"' for field in schema.key) + "]",
    ]
    if schema.group:
        lines.append(f'group = "{schema.group}"')
    lines.append(f'mode = "{schema.mode}"')
    return "\n".join(lines) + "\n"


def validate(schema: MemorySchema, config: Config) -> None:
    errors: list[FieldError] = []
    if not is_valid_slug(schema.type):
        errors.append(FieldError("type", "must be a kebab-case slug"))
    if not schema.description:
        errors.append(FieldError("description", "required"))
    if not schema.key:
        errors.append(FieldError("key", "at least one key field"))
    for field in schema.key:
        if field in RESERVED_FIELDS or not is_valid_slug(field.replace("_", "-")):
            errors.append(FieldError("key", f"not a usable field name: {field}"))
    if schema.group is not None:
        if schema.group not in schema.key:
            errors.append(FieldError("group", "the group field must be one of the key fields"))
        if source_of(schema.group, config) == SOURCE_FIELD:
            errors.append(
                FieldError("group", "a directory segment may only come from a system or menu field")
            )
    if schema.mode not in MODES:
        errors.append(FieldError("mode", f"must be one of {', '.join(MODES)}"))
    if errors:
        raise ValidationError(errors)


FACTORY: tuple[MemorySchema, ...] = (
    MemorySchema(
        "profile",
        "Who the person is: name, role, situation, standing circumstances. One file per person;"
        " write when the conversation states or changes such a fact about them.",
        ("user",),
        group=None,
    ),
    MemorySchema(
        "preference",
        "A stable habit, taste or way of working. Write one when the person says how they like"
        " things done, what they avoid, or what they always choose.",
        ("topic", "subject"),
        group="topic",
    ),
    MemorySchema(
        "entity",
        "A person, organisation, product or place the person deals with, and what is known"
        " about it. Write one when a named thing gets a durable attribute.",
        ("category", "subject"),
        group="category",
    ),
    MemorySchema(
        "event",
        "Something that happened on a date: a purchase, a trip, an incident, a milestone. At"
        " least one per session; each event is its own file with its own date.",
        ("date", "subject"),
        group="date",
        mode=MODE_ADD_ONLY,
    ),
    MemorySchema(
        "decision",
        "A choice made in a project and why. Write one when the conversation settles on"
        " an approach, rejects an alternative, or changes an earlier choice.",
        ("project", "subject"),
        group="project",
    ),
    MemorySchema(
        "procedure",
        "How a recurring task is done, step by step. Write one when a working sequence is"
        " established or corrected.",
        ("project", "subject"),
        group="project",
    ),
    MemorySchema(
        "fact",
        "A standing fact about a project: a constraint, a value, a configuration, a rule."
        " Write one when a specific value or rule is stated that a later task will need.",
        ("project", "subject"),
        group="project",
    ),
    MemorySchema(
        "experience",
        "A lesson: symptom, cause, fix. Write one when something went wrong and the fix was"
        " found, or when an approach turned out to work.",
        ("topic", "subject"),
        group="topic",
    ),
    MemorySchema(
        "reference",
        "Outside material worth keeping: a link, a title, a recommendation, a quoted source."
        " Write one when the conversation names material the person may return to.",
        ("source", "subject"),
        group="source",
    ),
)


class SchemaRegistry:
    """Reads the store's schema directory. The factory set is written once, on first use."""

    def __init__(self, layout: StoreLayout):
        self._layout = layout
        self._config = layout.config
        self._schemas: dict[str, MemorySchema] | None = None

    def ensure_factory(self) -> None:
        folder = self._layout.schemas_dir
        folder.mkdir(parents=True, exist_ok=True)
        if any(folder.glob("*" + SCHEMA_SUFFIX)):
            return
        for schema in FACTORY:
            (folder / f"{schema.type}{SCHEMA_SUFFIX}").write_text(render(schema), encoding="utf-8")
        self._schemas = None

    def load(self) -> dict[str, MemorySchema]:
        if self._schemas is not None:
            return self._schemas
        found: dict[str, MemorySchema] = {}
        folder = self._layout.schemas_dir
        if folder.is_dir():
            for path in sorted(folder.glob("*" + SCHEMA_SUFFIX)):
                schema = parse(path.read_text(encoding="utf-8"))
                validate(schema, self._config)
                if schema.type != path.stem:
                    raise ValidationError(
                        [FieldError("type", f"{path.name} declares type {schema.type}")]
                    )
                found[schema.type] = schema
        self._schemas = found
        return found

    def get(self, type_name: str) -> MemorySchema | None:
        return self.load().get(type_name)

    def require(self, type_name: str) -> MemorySchema:
        schema = self.get(type_name)
        if schema is None:
            known = ", ".join(sorted(self.load())) or "none"
            raise ValidationError([FieldError("type", f"unknown type {type_name}; known: {known}")])
        return schema

    def all(self) -> list[MemorySchema]:
        return list(self.load().values())

    def path_for(self, type_name: str) -> pathlib.Path:
        return self._layout.schemas_dir / f"{type_name}{SCHEMA_SUFFIX}"
