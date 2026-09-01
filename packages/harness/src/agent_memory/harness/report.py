"""Aggregation. Attribution is licensed only when every arm shares one recall fingerprint."""

from __future__ import annotations

import dataclasses

from .metrics import STATUS_OK

PERCENT = 100.0


@dataclasses.dataclass(frozen=True)
class ArmSummary:
    arm: str
    graded: int
    failed: int
    correct: int
    accuracy: float
    blocking_seconds: float
    experience_seconds: float
    exam_seconds: float
    memories: float


@dataclasses.dataclass(frozen=True)
class Report:
    arms: tuple[ArmSummary, ...]
    by_question_type: dict[str, dict[str, float]]
    recall_fingerprints: tuple[str, ...]
    episode_fingerprints: tuple[str, ...]

    def attribution_is_licensed(self) -> bool:
        return len(self.recall_fingerprints) == 1 and len(self.episode_fingerprints) == 1


def summarise(records: list[dict[str, object]]) -> Report:
    arms = sorted({str(record["arm"]) for record in records})
    summaries: list[ArmSummary] = []
    for arm in arms:
        rows = [record for record in records if record["arm"] == arm]
        graded = [row for row in rows if row["status"] == STATUS_OK]
        correct = [row for row in graded if row["correct"]]
        summaries.append(
            ArmSummary(
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

    by_type: dict[str, dict[str, float]] = {}
    for question_type in sorted({str(record["question_type"]) for record in records}):
        by_type[question_type] = {
            arm: _ratio(
                len(
                    [
                        record
                        for record in records
                        if record["arm"] == arm
                        and record["question_type"] == question_type
                        and record["status"] == STATUS_OK
                        and record["correct"]
                    ]
                ),
                len(
                    [
                        record
                        for record in records
                        if record["arm"] == arm
                        and record["question_type"] == question_type
                        and record["status"] == STATUS_OK
                    ]
                ),
            )
            for arm in arms
        }

    return Report(
        arms=tuple(summaries),
        by_question_type=by_type,
        recall_fingerprints=tuple(sorted({str(r["recall_fingerprint"]) for r in records})),
        episode_fingerprints=tuple(sorted({str(r["episode_fingerprint"]) for r in records})),
    )


def render(report: Report) -> str:
    lines = ["| arm | graded | correct | accuracy | blocking s | exam s | memories |",
             "|---|---|---|---|---|---|---|"]
    for summary in report.arms:
        lines.append(
            f"| {summary.arm} | {summary.graded} | {summary.correct} | "
            f"{summary.accuracy:.1f}% | {summary.blocking_seconds:.1f} | "
            f"{summary.exam_seconds:.1f} | {summary.memories:.1f} |"
        )
    lines.append("")
    header = " | ".join(summary.arm for summary in report.arms)
    lines.append(f"| question type | {header} |")
    lines.append("|---" * (len(report.arms) + 1) + "|")
    for question_type, scores in report.by_question_type.items():
        cells = " | ".join(f"{scores[summary.arm]:.1f}%" for summary in report.arms)
        lines.append(f"| {question_type} | {cells} |")
    lines.append("")
    lines.append(
        "attribution licensed: "
        f"{report.attribution_is_licensed()} "
        f"(recall fingerprints={list(report.recall_fingerprints)}, "
        f"episodes={list(report.episode_fingerprints)})"
    )
    return "\n".join(lines)


def _ratio(part: int, whole: int) -> float:
    return PERCENT * part / whole if whole else 0.0


def _mean(rows: list[dict[str, object]], key: str) -> float:
    values = [float(str(row[key])) for row in rows]
    return sum(values) / len(values) if values else 0.0
