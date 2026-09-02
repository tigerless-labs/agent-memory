"""Write coverage: did the gold answer reach any record at all?

Deterministic and offline — it reads the stores a run left behind and nothing else, so a
write-side change can be looked at before an exam is paid for. It is also the one quantity
that separates in a system-to-system comparison, because it looks only at what reached disk.
"""

from __future__ import annotations

import dataclasses
import json
import pathlib
import re

from . import arms as arms_module
from . import systems
from .dataset import ABSTENTION_MARKER

DEFAULT_THRESHOLD = 0.6
MIN_WORD_LENGTH = 3
WORD = re.compile(r"[a-z0-9]+")
STOP_WORDS = frozenset(
    {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being", "of", "to", "in",
        "on", "at", "for", "with", "and", "or", "but", "if", "you", "your", "i", "my", "it",
        "its", "that", "this", "these", "those", "they", "them", "he", "she", "his", "her",
        "as", "by", "from", "what", "when", "where", "who", "how", "much", "many", "do",
        "does", "did", "have", "has", "had", "will", "would", "can", "could", "there",
        "their", "about", "into", "over", "than", "then", "so", "not", "no", "yes",
    }
)


@dataclasses.dataclass(frozen=True)
class CoverageRow:
    system: str
    arm: str
    answerable: int
    covered: int

    @property
    def rate(self) -> float:
        return self.covered / self.answerable if self.answerable else 0.0

    def as_dict(self) -> dict[str, object]:
        return dataclasses.asdict(self) | {"rate": round(self.rate, RATE_PRECISION)}


def covers(text: str, gold: str, threshold: float = DEFAULT_THRESHOLD) -> bool:
    wanted = _words(gold)
    if not wanted:
        return False
    return len(wanted & _words(text)) / len(wanted) >= threshold


def probe(
    records: list[dict[str, object]],
    stores: pathlib.Path,
    threshold: float = DEFAULT_THRESHOLD,
) -> list[CoverageRow]:
    tallies: dict[tuple[str, str], list[int]] = {}
    for record in records:
        arm = str(record["arm"])
        known = arms_module.BY_NAME.get(arm)
        if known is not None and not known.memory:
            continue
        episode_id = str(record["episode_id"])
        if episode_id.endswith(ABSTENTION_MARKER):
            continue
        system = str(record.get("system", systems.NATIVE))
        root = stores / arm / episode_id
        texts = systems.texts_of(system, root) if root.exists() else []
        hit = any(covers(text, str(record["expected"]), threshold) for text in texts)
        tally = tallies.setdefault((system, arm), [0, 0])
        tally[0] += 1
        tally[1] += int(hit)
    return [
        CoverageRow(system=system, arm=arm, answerable=answerable, covered=covered)
        for (system, arm), (answerable, covered) in sorted(tallies.items())
    ]


def render(rows: list[CoverageRow]) -> str:
    lines = ["| system | arm | answer reached a record |", "|---|---|---|"]
    for row in rows:
        lines.append(
            f"| {row.system} | {row.arm} | {row.covered}/{row.answerable} "
            f"= {PERCENT * row.rate:.1f}% |"
        )
    return "\n".join(lines)


def as_json(rows: list[CoverageRow]) -> str:
    return json.dumps([row.as_dict() for row in rows], indent=JSON_INDENT)


def _words(text: str) -> set[str]:
    return {
        word
        for word in WORD.findall(text.lower())
        if word not in STOP_WORDS and len(word) >= MIN_WORD_LENGTH
    }


PERCENT = 100.0
RATE_PRECISION = 4
JSON_INDENT = 2
