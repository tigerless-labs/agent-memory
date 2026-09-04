"""Upgrades a four-domain store into the schema layout. Human-run, once, idempotent.

The old layout kept a fixed domain as the first path segment and a type inside it; the new
layout keeps the type first and a group under it (ADR-008). Every old file becomes a file of
the matching factory type, grouped by its old domain so that no directory name has to be
invented. Old statuses collapse into the two-state model (ADR-009): retired files and
superseded files become invalid, stale files become active.
"""

from __future__ import annotations

import dataclasses
import pathlib
import tomllib

from . import frontmatter
from .config import CONFIG_FILENAME, Config, StorageConfig
from .paths import ARCHIVE_DIRNAME, MEMORY_SUFFIX
from .record import STATUS_ACTIVE, STATUS_INVALID
from .store import Store

LEGACY_DOMAINS = ("user", "project", "reference", "experience")
LEGACY_RETIRED_DIRNAME = "retired"
LEGACY_STATUS_RETIRED = "retired"
LEGACY_STATUS_STALE = "stale"
LEGACY_RETIRED_DOMAIN_INDEX = 2
LEGACY_TYPE_MAP = {
    ("user", "fact"): "fact",
    ("user", "preference"): "preference",
    ("project", "fact"): "fact",
    ("project", "decision"): "decision",
    ("project", "procedure"): "procedure",
    ("experience", "experience"): "experience",
    ("experience", "procedure"): "procedure",
    ("reference", "reference"): "reference",
}
REMOVED_KNOBS = {
    "storage": ("domains", "domain_types", "max_depth_below_domain"),
    "manage": ("stale_after_days", "authority"),
}


@dataclasses.dataclass(frozen=True)
class MigrationReport:
    moved: tuple[str, ...]
    invalidated: tuple[str, ...]
    skipped: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "moved": list(self.moved),
            "invalidated": list(self.invalidated),
            "skipped": list(self.skipped),
        }


def needs_migration(root: pathlib.Path) -> bool:
    return any(_legacy_files(root))


def migrate(root: pathlib.Path) -> MigrationReport:
    _upgrade_config(root)
    store = Store(root)
    store.init()
    moved: list[str] = []
    invalidated: list[str] = []
    skipped: list[str] = []
    for path, retired in _legacy_files(root):
        fields, body = frontmatter.parse(path.read_text(encoding="utf-8"))
        domain = _legacy_domain(root, path)
        new_type: str | None = LEGACY_TYPE_MAP.get((domain, str(fields.get("type") or "")))
        if new_type is None or not fields.get("name"):
            skipped.append(str(path.relative_to(root)))
            continue
        schema = store.schemas.get(new_type)
        if schema is None or schema.group is None:
            skipped.append(str(path.relative_to(root)))
            continue
        fields["type"] = new_type
        fields[schema.group] = domain
        for key_field in schema.key:
            fields.setdefault(key_field, str(fields.get("name")))
        status = str(fields.get("status") or STATUS_ACTIVE)
        if retired or status == LEGACY_STATUS_RETIRED or fields.get("superseded_by"):
            fields["status"] = STATUS_INVALID
            fields.setdefault("invalid_at", fields.get("updated"))
            if not fields.get("invalid_at"):
                fields["invalid_at"] = fields.get("updated")
            invalidated.append(str(fields["name"]))
        elif status == LEGACY_STATUS_STALE:
            fields["status"] = STATUS_ACTIVE
        target = store.layout.type_dir(new_type) / domain / (str(fields["name"]) + MEMORY_SUFFIX)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(frontmatter.render(fields, body), encoding="utf-8")
        path.unlink()
        moved.append(str(target.relative_to(root)))
    _remove_empty_legacy_dirs(root)
    store.rebuild_index()
    return MigrationReport(tuple(moved), tuple(invalidated), tuple(skipped))


def _legacy_files(root: pathlib.Path) -> list[tuple[pathlib.Path, bool]]:
    found: list[tuple[pathlib.Path, bool]] = []
    for domain in LEGACY_DOMAINS:
        folder = root / domain
        if folder.is_dir():
            found.extend((path, False) for path in sorted(folder.rglob("*" + MEMORY_SUFFIX)))
    retired = root / ARCHIVE_DIRNAME / LEGACY_RETIRED_DIRNAME
    if retired.is_dir():
        found.extend((path, True) for path in sorted(retired.rglob("*" + MEMORY_SUFFIX)))
    return found


def _legacy_domain(root: pathlib.Path, path: pathlib.Path) -> str:
    parts = path.relative_to(root).parts
    if parts[0] == ARCHIVE_DIRNAME:
        return (
            parts[LEGACY_RETIRED_DOMAIN_INDEX]
            if len(parts) > len(("archive", "retired", "file"))
            else parts[1]
        )
    return parts[0]


def _upgrade_config(root: pathlib.Path) -> None:
    path = root / CONFIG_FILENAME
    if not path.exists():
        return
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    changed = False
    for section, knobs in REMOVED_KNOBS.items():
        for knob in knobs:
            if knob in raw.get(section, {}):
                del raw[section][knob]
                changed = True
    if not changed:
        return
    config = Config.default()
    for section_name, values in raw.items():
        target = getattr(config, section_name, None)
        if target is None:
            continue
        for key, value in values.items():
            if hasattr(target, key):
                setattr(target, key, value)
    config.storage = dataclasses.replace(
        StorageConfig(), slug_max_length=config.storage.slug_max_length
    )
    config.save(root)


def _remove_empty_legacy_dirs(root: pathlib.Path) -> None:
    candidates = [root / domain for domain in LEGACY_DOMAINS]
    candidates.append(root / ARCHIVE_DIRNAME / LEGACY_RETIRED_DIRNAME)
    for folder in candidates:
        if not folder.is_dir():
            continue
        for child in sorted(folder.rglob("*"), key=lambda item: -len(item.parts)):
            if child.is_dir() and not any(child.iterdir()):
                child.rmdir()
        if not any(folder.iterdir()):
            folder.rmdir()
