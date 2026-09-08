"""Physical layout of a memory store. The only module that knows directory names."""

from __future__ import annotations

import dataclasses
import pathlib

from .config import Config

MEMORY_INDEX_FILENAME = "MEMORY.md"
ARCHIVE_DIRNAME = "archive"
PROVENANCE_DIRNAME = "provenance"
SESSIONS_DIRNAME = "sessions"
INDEX_DIRNAME = ".index"
STATE_DIRNAME = ".state"
INDEX_DB_FILENAME = "index.db"
LOCK_FILENAME = "store.lock"
MEMORY_SUFFIX = ".md"


@dataclasses.dataclass(frozen=True)
class StoreLayout:
    root: pathlib.Path
    config: Config

    @property
    def memory_index(self) -> pathlib.Path:
        return self.root / MEMORY_INDEX_FILENAME

    @property
    def archive(self) -> pathlib.Path:
        return self.root / ARCHIVE_DIRNAME

    @property
    def provenance(self) -> pathlib.Path:
        return self.archive / PROVENANCE_DIRNAME

    @property
    def sessions(self) -> pathlib.Path:
        return self.archive / SESSIONS_DIRNAME

    @property
    def schemas_dir(self) -> pathlib.Path:
        return self.root / self.config.storage.schemas_dirname

    @property
    def index_dir(self) -> pathlib.Path:
        return self.root / INDEX_DIRNAME

    @property
    def index_db(self) -> pathlib.Path:
        return self.index_dir / INDEX_DB_FILENAME

    @property
    def state_dir(self) -> pathlib.Path:
        return self.root / STATE_DIRNAME

    @property
    def lock_file(self) -> pathlib.Path:
        return self.state_dir / LOCK_FILENAME

    @property
    def watermarks(self) -> pathlib.Path:
        return self.state_dir / self.config.write.watermark_dirname

    @property
    def pending(self) -> pathlib.Path:
        return self.state_dir / self.config.write.pending_dirname

    @property
    def dream_reports(self) -> pathlib.Path:
        return self.root / self.config.manage.dream_report_dirname

    @property
    def reserved_dirnames(self) -> frozenset[str]:
        return frozenset(
            {
                ARCHIVE_DIRNAME,
                INDEX_DIRNAME,
                STATE_DIRNAME,
                self.config.storage.schemas_dirname,
                self.config.manage.dream_report_dirname,
            }
        )

    def type_dir(self, type_name: str) -> pathlib.Path:
        return self.root / type_name

    def ensure(self) -> None:
        for path in (
            self.root,
            self.archive,
            self.provenance,
            self.sessions,
            self.schemas_dir,
            self.index_dir,
            self.state_dir,
            self.watermarks,
            self.dream_reports,
        ):
            path.mkdir(parents=True, exist_ok=True)
        if not self.memory_index.exists():
            self.memory_index.write_text(self.config.memory_md.header + "\n\n", encoding="utf-8")

    def type_of(self, path: pathlib.Path) -> str | None:
        try:
            relative = pathlib.Path(path).resolve().relative_to(self.root.resolve())
        except ValueError:
            return None
        parts = relative.parts
        if len(parts) < len(("type", "file")) or parts[0] in self.reserved_dirnames:
            return None
        if relative.suffix != MEMORY_SUFFIX:
            return None
        return parts[0]

    def groups_of(self, type_name: str) -> set[str]:
        folder = self.type_dir(type_name)
        if not folder.is_dir():
            return set()
        return {entry.name for entry in folder.iterdir() if entry.is_dir()}

    def truth_files(self) -> list[pathlib.Path]:
        files: list[pathlib.Path] = []
        if not self.root.is_dir():
            return files
        for entry in sorted(self.root.iterdir()):
            if not entry.is_dir() or entry.name in self.reserved_dirnames:
                continue
            files.extend(sorted(entry.rglob("*" + MEMORY_SUFFIX)))
        return files
