"""Grading. Held identical across arms, so a score difference can only come from W."""

from __future__ import annotations

import dataclasses
import re

from .hosts import Host

VERDICT_YES = "yes"
RUBRIC = """You are grading one answer against the reference answer.

Question: {question}
Reference answer: {expected}
Candidate answer: {candidate}

The candidate is correct when it conveys the reference answer's information, allowing for
different wording, extra detail, or a different level of precision that stays consistent with
the reference. The candidate is incorrect when it contradicts the reference, omits the part the
question asks for, or declines to answer.

Reply with exactly one word: yes or no."""

_WORD = re.compile(r"[a-z]+")


@dataclasses.dataclass(frozen=True)
class Verdict:
    correct: bool
    seconds: float
    ok: bool
    raw: str


class Judge:
    def __init__(self, host: Host):
        self._host = host

    @property
    def model(self) -> str:
        return self._host.spec.model

    def grade(self, question: str, expected: str, candidate: str) -> Verdict:
        if not candidate.strip():
            return Verdict(correct=False, seconds=0.0, ok=True, raw="")
        prompt = RUBRIC.format(question=question, expected=expected, candidate=candidate)
        result = self._host.run(prompt)
        words = _WORD.findall(result.text.lower())
        return Verdict(
            correct=bool(words) and words[0] == VERDICT_YES,
            seconds=result.seconds,
            ok=result.ok,
            raw=result.text[:RAW_EXCERPT],
        )


RAW_EXCERPT = 120
