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

First read the REFERENCE alone and decide which of three kinds it is. Exactly one applies.

ABSENCE — the reference says the information was never provided ("you did not mention this",
"the information provided is not enough"). It may add what the person did mention instead;
that is context, not something the candidate has to repeat.
  correct: the candidate reports having no record of what was asked, in any wording.
  incorrect: the candidate names an answer, including a hedged or most-likely one.

STANDARD — the reference does not answer, it describes what a good answer must satisfy ("the
user would prefer suggestions that ...", often with "they may not prefer ..."). The question
asked for suggestions.
  correct: what the candidate proposes is the kind of thing the reference says this person
    wants, and avoids what it says they do not. The candidate will not restate the preference
    and is not expected to — judge its suggestions.
  incorrect: the suggestions ignore the standard, or the candidate makes no suggestions at all.

FACT — the reference states an answer.
  correct: the candidate conveys the same answer. Form does not matter: "9" for "nine", "five
    tops" for "5", "Five issues of National Geographic" for "Five", a reformatted date,
    "approximately" in front of the same value, or extra detail that agrees.
  incorrect: a different value, a range or floor where the reference gives a figure ("at least
    4" for "six"), swapped terms of a comparison, the part asked for missing, or the candidate
    saying it does not have the information — under FACT, not knowing is wrong.

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

