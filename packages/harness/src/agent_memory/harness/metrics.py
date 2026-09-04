"""One structured record per run. Everything the report needs, nothing it has to infer."""

from __future__ import annotations

import dataclasses
import json
import pathlib

from .systems import NATIVE as NATIVE_SYSTEM

STATUS_OK = "ok"
STATUS_FAILED = "failed"
RECORDS_FILENAME = "runs.jsonl"
RUN_METADATA_FILENAME = "run.json"


@dataclasses.dataclass(frozen=True)
class RunRecord:
    run_id: str
    arm: str
    host: str
    episode_id: str
    question_type: str
    status: str
    correct: bool
    answer: str
    expected: str
    memories_written: int
    experience_calls: int
    experience_seconds: float
    blocking_seconds: float
    exam_seconds: float
    judge_seconds: float
    recall_fingerprint: str
    episode_fingerprint: str
    error: str = ""
    manage: str = ""
    system: str = NATIVE_SYSTEM
    recall_names: tuple[str, ...] = ()
    raw_recall_names: tuple[str, ...] = ()
    read_names: tuple[str, ...] = ()
    recall_queries: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class RunMetadata:
    run_id: str
    system: str
    host: str
    model: str
    judge_model: str
    exam_mode: str
    episode_fingerprint: str
    reuse_stores: str | None
    config: dict[str, object]
    code_revision: str

    def as_dict(self) -> dict[str, object]:
        return dataclasses.asdict(self)


class RunMetadataSink:
    def __init__(self, folder: pathlib.Path):
        self._folder = folder
        self._path = folder / RUN_METADATA_FILENAME

    def ensure(self, metadata: RunMetadata, resume: bool = False) -> None:
        expected = json.loads(json.dumps(metadata.as_dict()))
        if self._path.exists():
            existing = json.loads(self._path.read_text(encoding="utf-8"))
            if existing != expected:
                raise ValueError("run metadata belongs to another experiment")
            return
        if resume and (self._folder / RECORDS_FILENAME).exists():
            raise ValueError("resume refused: existing records have no run metadata")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(expected, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


class MetricsSink:
    def __init__(self, folder: pathlib.Path):
        self._path = folder / RECORDS_FILENAME
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> pathlib.Path:
        return self._path

    def append(self, record: RunRecord) -> None:
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.as_dict(), sort_keys=True) + "\n")

    def replace(self, records: list[dict[str, object]]) -> None:
        self._path.write_text(
            "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
            encoding="utf-8",
        )

    def records(self) -> list[dict[str, object]]:
        if not self._path.exists():
            return []
        return [
            json.loads(line)
            for line in self._path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
