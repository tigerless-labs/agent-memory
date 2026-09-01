"""Physical layout of a memory store. The only module that knows directory names."""

from __future__ import annotations

import dataclasses
import pathlib

from .config import Config

MEMORY_INDEX_FILENAME = "MEMORY.md"
ARCHIVE_DIRNAME = "archive"
PROVENANCE_DIRNAME = "provenance"
RETIRED_DIRNAME = "retired"
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
    def retired(self) -> pathlib.Path:
        return self.archive / RETIRED_DIRNAME

    @property
    def sessions(self) -> pathlib.Path:
        return self.archive / SESSIONS_DIRNAME

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
    def dream_reports(self) -> pathlib.Path:
        return self.root / self.config.manage.dream_report_dirname

    def domain_dir(self, domain: str) -> pathlib.Path:
        return self.root / domain

    def ensure(self) -> None:
        for path in (
            self.root,
            self.archive,
            self.provenance,
            self.retired,
            self.sessions,
            self.index_dir,
            self.state_dir,
            self.watermarks,
            self.dream_reports,
        ):
            path.mkdir(parents=True, exist_ok=True)
        for domain in self.config.storage.domains:
            self.domain_dir(domain).mkdir(parents=True, exist_ok=True)
        if not self.memory_index.exists():
            self.memory_index.write_text(
                self.config.memory_md.header + "\n\n", encoding="utf-8"
            )

    def domain_of(self, path: pathlib.Path) -> str | None:
        try:
            relative = pathlib.Path(path).resolve().relative_to(self.root)
        except ValueError:
            return None
        parts = relative.parts
        if parts and parts[0] == ARCHIVE_DIRNAME:
            parts = parts[1:]
        if parts and parts[0] == RETIRED_DIRNAME:
            parts = parts[1:]
        head = parts[0] if parts else ""
        return head if head in self.config.storage.domains else None

    def is_archived(self, path: pathlib.Path) -> bool:
        try:
            pathlib.Path(path).resolve().relative_to(self.archive)
        except ValueError:
            return False
        return True

    def truth_files(self) -> list[pathlib.Path]:
        files: list[pathlib.Path] = []
        for domain in self.config.storage.domains:
            files.extend(sorted(self.domain_dir(domain).rglob("*" + MEMORY_SUFFIX)))
        return files

    def archived_files(self) -> list[pathlib.Path]:
        return sorted(self.retired.rglob("*" + MEMORY_SUFFIX))
