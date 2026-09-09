"""Export/import. Migration freedom is the point of file truth (ADR-001), so it must be cheap."""

from __future__ import annotations

import json
import pathlib

from .archive import SESSION_SUFFIX
from .paths import MEMORY_SUFFIX, StoreLayout
from .store import Store

EXPORT_INDENT = 2
FORMAT_VERSION = "agent-memory/export/v1"
KEY_VERSION = "format"
KEY_FILES = "files"
KEY_PATH = "path"
KEY_TEXT = "text"


def export_store(store: Store, include_archive: bool = True) -> dict[str, object]:
    payload: list[dict[str, str]] = []
    for path in _sources(store.layout, include_archive):
        payload.append(
            {
                KEY_PATH: str(path.relative_to(store.root)),
                KEY_TEXT: path.read_text(encoding="utf-8"),
            }
        )
    return {KEY_VERSION: FORMAT_VERSION, KEY_FILES: payload}


def write_export(store: Store, target: pathlib.Path, include_archive: bool = True) -> pathlib.Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(export_store(store, include_archive), indent=EXPORT_INDENT, sort_keys=True),
        encoding="utf-8",
    )
    return target


def import_into(store: Store, payload: dict[str, object]) -> int:
    if payload.get(KEY_VERSION) != FORMAT_VERSION:
        raise ValueError(f"unsupported export format: {payload.get(KEY_VERSION)}")
    store.layout.ensure()
    files = payload.get(KEY_FILES)
    written = 0
    for entry in files if isinstance(files, list) else []:
        target = (store.root / str(entry[KEY_PATH])).resolve()
        if not target.is_relative_to(store.root.resolve()):
            raise ValueError(f"path traversal refused: {entry[KEY_PATH]}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(entry[KEY_TEXT]), encoding="utf-8")
        written += 1
    store.rebuild_index()
    return written


def read_import(store: Store, source: pathlib.Path) -> int:
    return import_into(store, json.loads(source.read_text(encoding="utf-8")))


def _sources(layout: StoreLayout, include_archive: bool) -> list[pathlib.Path]:
    paths = layout.truth_files()
    if include_archive:
        paths = paths + sorted(layout.archive.rglob("*"))
    keep = (MEMORY_SUFFIX, SESSION_SUFFIX)
    return [path for path in paths if path.is_file() and path.suffix in keep]
