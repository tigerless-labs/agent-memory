"""One structured record per run. Everything the report needs, nothing it has to infer."""

from __future__ import annotations

import dataclasses
import json
import pathlib

from .systems import NATIVE as NATIVE_SYSTEM

STATUS_OK = "ok"
STATUS_FAILED = "failed"
RECORDS_FILENAME = "runs.jsonl"


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
    system: str = NATIVE_SYSTEM

    def as_dict(self) -> dict[str, object]:
        return dataclasses.asdict(self)


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
