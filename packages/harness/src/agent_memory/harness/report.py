"""Aggregation. Attribution is licensed only when every arm shares one recall fingerprint."""

from __future__ import annotations

import dataclasses

from .metrics import STATUS_OK
from .systems import NATIVE

PERCENT = 100.0
LABEL_SEPARATOR = "/"


@dataclasses.dataclass(frozen=True)
class ArmSummary:
    system: str
    arm: str
    graded: int
    failed: int
    correct: int
    accuracy: float
    blocking_seconds: float
    experience_seconds: float
    exam_seconds: float
    memories: float

    @property
    def label(self) -> str:
        return f"{self.system}{LABEL_SEPARATOR}{self.arm}"


@dataclasses.dataclass(frozen=True)
class Report:
    arms: tuple[ArmSummary, ...]
    by_question_type: dict[str, dict[str, float]]
    recall_fingerprints: tuple[str, ...]
    episode_fingerprints: tuple[str, ...]

    def attribution_is_licensed(self) -> bool:
        return len(self.recall_fingerprints) == 1 and len(self.episode_fingerprints) == 1

    def label_of(self, summary: ArmSummary) -> str:
        """Arms are named by W alone until a second system makes that ambiguous."""
        multiple = len({row.system for row in self.arms}) > 1
        return summary.label if multiple else summary.arm


def summarise(records: list[dict[str, object]]) -> Report:
    keys = sorted({(_system_of(record), str(record["arm"])) for record in records})
    summaries: list[ArmSummary] = []
    for system, arm in keys:
        rows = [r for r in records if _system_of(r) == system and r["arm"] == arm]
        graded = [row for row in rows if row["status"] == STATUS_OK]
        correct = [row for row in graded if row["correct"]]
        summaries.append(
            ArmSummary(
                system=system,
                arm=arm,
                graded=len(graded),
                failed=len(rows) - len(graded),
                correct=len(correct),
                accuracy=_ratio(len(correct), len(graded)),
                blocking_seconds=_mean(rows, "blocking_seconds"),
                experience_seconds=_mean(rows, "experience_seconds"),
                exam_seconds=_mean(rows, "exam_seconds"),
                memories=_mean(rows, "memories_written"),
            )
        )

    report = Report(
        arms=tuple(summaries),
        by_question_type={},
        recall_fingerprints=tuple(sorted({str(r["recall_fingerprint"]) for r in records})),
        episode_fingerprints=tuple(sorted({str(r["episode_fingerprint"]) for r in records})),
    )
    by_type: dict[str, dict[str, float]] = {}
    for question_type in sorted({str(record["question_type"]) for record in records}):
        by_type[question_type] = {
            report.label_of(summary): _accuracy_of(
                records, summary.system, summary.arm, question_type
            )
            for summary in summaries
        }
    return dataclasses.replace(report, by_question_type=by_type)


def render(report: Report) -> str:
    lines = [
        "| system | arm | graded | correct | accuracy | blocking s | exam s | memories |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for summary in report.arms:
        lines.append(
            f"| {summary.system} | {summary.arm} | {summary.graded} | {summary.correct} | "
            f"{summary.accuracy:.1f}% | {summary.blocking_seconds:.1f} | "
            f"{summary.exam_seconds:.1f} | {summary.memories:.1f} |"
        )
    lines.append("")
    labels = [report.label_of(summary) for summary in report.arms]
    lines.append(f"| question type | {' | '.join(labels)} |")
    lines.append("|---" * (len(labels) + 1) + "|")
    for question_type, scores in report.by_question_type.items():
        cells = " | ".join(f"{scores[label]:.1f}%" for label in labels)
        lines.append(f"| {question_type} | {cells} |")
    lines.append("")
    lines.append(
        "attribution licensed: "
        f"{report.attribution_is_licensed()} "
        f"(recall fingerprints={list(report.recall_fingerprints)}, "
        f"episodes={list(report.episode_fingerprints)})"
    )
    return "\n".join(lines)


def _accuracy_of(
    records: list[dict[str, object]], system: str, arm: str, question_type: str
) -> float:
    graded = [
        record
        for record in records
        if _system_of(record) == system
        and record["arm"] == arm
        and record["question_type"] == question_type
        and record["status"] == STATUS_OK
    ]
    return _ratio(len([record for record in graded if record["correct"]]), len(graded))


def _system_of(record: dict[str, object]) -> str:
    return str(record.get("system", NATIVE))


def _ratio(part: int, whole: int) -> float:
    return PERCENT * part / whole if whole else 0.0


def _mean(rows: list[dict[str, object]], key: str) -> float:
    values = [float(str(row[key])) for row in rows]
    return sum(values) / len(values) if values else 0.0
