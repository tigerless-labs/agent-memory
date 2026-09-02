"""LoCoMo, converted into the one shape the driver replays.

A second benchmark earns its keep only if it asks something the first cannot. LoCoMo's
conversations are two named people talking across dated sessions, and its questions are graded
by category — including a category whose honest answer is that the conversation never said.
That last one is why it is worth converting: abstention is where a memory system's failure
mode is confident invention rather than a miss.

Converting rather than adapting is deliberate. The driver, the isolation gate and the report
stay unaware there is a second suite at all, which is the only way two benchmarks stay
comparable to each other.
"""

from __future__ import annotations

import json
import pathlib
import re

from .dataset import (
    ABSTENTION_MARKER,
    KEY_ANSWER,
    KEY_CONTENT,
    KEY_DATES,
    KEY_EVIDENCE,
    KEY_QUESTION,
    KEY_QUESTION_DATE,
    KEY_QUESTION_ID,
    KEY_QUESTION_TYPE,
    KEY_ROLE,
    KEY_SESSION_IDS,
    KEY_SESSIONS,
    ROLE_USER,
)

CATEGORIES = {
    1: "multi-hop",
    2: "temporal-reasoning",
    3: "open-domain",
    4: "single-hop",
    5: "unanswerable",
}
UNANSWERABLE = 5
SAMPLE_ID = "sample_id"
CONVERSATION = "conversation"
QA = "qa"
CATEGORY = "category"
ADVERSARIAL_ANSWER = "adversarial_answer"
SPEAKER = "speaker"
TEXT = "text"
DIALOGUE_ID = "dia_id"
SESSION_PREFIX = "session_"
DATE_SUFFIX = "_date_time"
SPEAKER_SEPARATOR = ": "
_SESSION = re.compile(r"^session_(\d+)$")
_EVIDENCE = re.compile(r"^D(\d+):")


def convert(source: pathlib.Path, target: pathlib.Path) -> int:
    entries = [
        entry
        for sample in json.loads(source.read_text(encoding="utf-8"))
        for entry in _entries(sample)
    ]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(entries), encoding="utf-8")
    return len(entries)


def _entries(sample: dict) -> list[dict]:
    conversation = sample[CONVERSATION]
    sessions = _sessions(conversation)
    identifiers = [name for name, _, _ in sessions]
    return [
        {
            KEY_QUESTION_ID: _identifier(sample, index, question),
            KEY_QUESTION: str(question[KEY_QUESTION]),
            KEY_ANSWER: str(
                question.get(KEY_ANSWER, question.get(ADVERSARIAL_ANSWER, ""))
            ),
            KEY_QUESTION_TYPE: CATEGORIES.get(
                int(question.get(CATEGORY, 0)), CATEGORIES[UNANSWERABLE]
            ),
            KEY_QUESTION_DATE: sessions[-1][1] if sessions else "",
            KEY_SESSION_IDS: identifiers,
            KEY_DATES: [date for _, date, _ in sessions],
            KEY_SESSIONS: [turns for _, _, turns in sessions],
            KEY_EVIDENCE: _evidence(question, identifiers),
        }
        for index, question in enumerate(sample[QA])
    ]


def _sessions(conversation: dict) -> list[tuple[str, str, list[dict]]]:
    numbered = sorted(
        (int(match[1]), key)
        for key in conversation
        if (match := _SESSION.match(key)) and isinstance(conversation[key], list)
    )
    return [
        (
            key,
            str(conversation.get(key + DATE_SUFFIX, "")),
            [
                {
                    KEY_ROLE: ROLE_USER,
                    KEY_CONTENT: str(turn.get(SPEAKER, ""))
                    + SPEAKER_SEPARATOR
                    + str(turn.get(TEXT, "")),
                }
                for turn in conversation[key]
            ],
        )
        for _, key in numbered
    ]


def _evidence(question: dict, identifiers: list[str]) -> list[str]:
    found = []
    for reference in question.get("evidence") or []:
        match = _EVIDENCE.match(str(reference))
        name = SESSION_PREFIX + match[1] if match else ""
        if name in identifiers and name not in found:
            found.append(name)
    return found


def _identifier(sample: dict, index: int, question: dict) -> str:
    """Stable across conversions, and carrying the marker the harness reads abstention from."""
    stem = f"{sample.get(SAMPLE_ID, 'locomo')}-{index}"
    unanswerable = int(question.get(CATEGORY, 0)) == UNANSWERABLE
    return stem + ABSTENTION_MARKER if unanswerable else stem
