"""Grading. Held identical across arms, so a score difference can only come from W."""

from __future__ import annotations

import concurrent.futures
import dataclasses
import re

from .hosts import Host
from .metrics import STATUS_OK

VERDICT_YES = "yes"
RUBRIC = """Decide whether a candidate answer is correct against a reference answer.

Question: {question}
Reference answer: {expected}
Candidate answer: {candidate}

Work in two steps.

Step 1. Look only at the REFERENCE answer, and ignore the candidate for now. Does the reference
itself say that the information was never provided — that the question asks about something the
person never mentioned? References of that kind say so outright, in wording such as "you did not
mention this" or "the information provided is not enough". Settle this before reading on.

Step 2a. If the reference DOES say the information was never provided, then reporting that the
information is absent IS the right answer, and the candidate agrees with the reference by
saying so. Judge it correct whenever it reports having no record of the thing asked about, in any
wording.
Such a reference often adds what the person did mention instead; that addition is context, not
part of what the candidate has to say, so a candidate that omits it is still correct.
Judge it incorrect only when it names a specific answer, including a hedged or most-likely one.

Step 2b. If the reference DOES give a substantive answer: judge the candidate correct when it
conveys that same information, and incorrect when it contradicts the reference, omits the part
the question asks for, or reports that it does not have the information — in this branch, not
having the information is a wrong answer.

Judging whether the same information is conveyed is a question about the answer, not about how
it is written. The candidate is still correct when it writes a quantity the other way round
("9" for "nine", "five tops" for "5"), restates the unit or the noun ("Five issues of National
Geographic" for "Five"), reformats a date, hedges with a word like "approximately" while
landing on the same value, or adds supporting detail that agrees with the reference. It becomes
incorrect when the value itself differs, when it gives a range or floor where the reference
gives a figure ("at least 4" for "six"), or when it swaps the terms of a comparison.

Reply with exactly one word: yes or no."""

_WORD = re.compile(r"[a-z]+")
DEFAULT_VOTES = 5
MAJORITY = 2
RAW_EXCERPT = 120
VOTE_EXCERPT = 20


@dataclasses.dataclass(frozen=True)
class Verdict:
    correct: bool
    seconds: float
    ok: bool
    raw: str


class Judge:
    """An LLM grader is a noisy instrument. Repeated votes are how the noise gets bounded."""

    def __init__(self, host: Host, votes: int = DEFAULT_VOTES):
        self._host = host
        self._votes = votes

    @property
    def model(self) -> str:
        return self._host.spec.model

    def grade(self, question: str, expected: str, candidate: str) -> Verdict:
        if not candidate.strip():
            return Verdict(correct=False, seconds=0.0, ok=True, raw="")
        prompt = RUBRIC.format(question=question, expected=expected, candidate=candidate)
        with concurrent.futures.ThreadPoolExecutor(max_workers=self._votes) as pool:
            results = list(pool.map(lambda _: self._host.run(prompt), range(self._votes)))
        usable = [result for result in results if result.ok]
        yeses = len([result for result in usable if _says_yes(result.text)])
        return Verdict(
            correct=bool(usable) and yeses > len(usable) / MAJORITY,
            seconds=sum(result.seconds for result in results),
            ok=bool(usable),
            raw=" | ".join(result.text[:VOTE_EXCERPT] for result in results),
        )



def regrade(
    records: list[dict[str, object]],
    judge: Judge,
    questions: dict[str, str],
    workers: int,
) -> list[dict[str, object]]:
    """Re-decide stored answers. The judge is an experiment variable, so changing it must
    not cost another host run."""

    def grade(record: dict[str, object]) -> dict[str, object]:
        if record["status"] != STATUS_OK:
            return record
        verdict = judge.grade(
            questions.get(str(record["episode_id"]), ""),
            str(record["expected"]),
            str(record["answer"]),
        )
        return record | {"correct": bool(verdict.correct and verdict.ok)}

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(grade, records))


def _says_yes(text: str) -> bool:
    words = _WORD.findall(text.lower())
    return bool(words) and words[0] == VERDICT_YES

