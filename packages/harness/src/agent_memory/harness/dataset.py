"""Benchmarks reduced to one shape: an episode is sessions to live through, then a question."""

from __future__ import annotations

import dataclasses
import datetime
import json
import pathlib

ROLE_USER = "user"
KEY_QUESTION_ID = "question_id"
KEY_QUESTION_TYPE = "question_type"
KEY_QUESTION = "question"
KEY_ANSWER = "answer"
KEY_QUESTION_DATE = "question_date"
KEY_SESSIONS = "haystack_sessions"
KEY_SESSION_IDS = "haystack_session_ids"
KEY_DATES = "haystack_dates"
KEY_EVIDENCE = "answer_session_ids"
KEY_ROLE = "role"
KEY_CONTENT = "content"
ABSTENTION_MARKER = "_abs"


@dataclasses.dataclass(frozen=True)
class Turn:
    role: str
    content: str


@dataclasses.dataclass(frozen=True)
class Session:
    id: str
    date: str
    turns: tuple[Turn, ...]

    def render(self) -> str:
        lines = [f"## Session {self.id} — {self.date}"]
        lines.extend(f"{turn.role}: {turn.content}" for turn in self.turns)
        return "\n".join(lines)

    def messages(self) -> list[dict[str, object]]:
        """The turns as the archive takes them, each stamped with the session's own date, so
        the executor dates what it writes by when it was said rather than by when it ran."""
        stamp = session_stamp(self.date)
        return [{"role": turn.role, "text": turn.content, "at": stamp} for turn in self.turns]


def session_stamp(date: str) -> str:
    """LongMemEval writes `2023/05/20 (Sat) 02:21`; the archive wants an instant."""
    parts = date.replace("/", "-").split()
    day = parts[0] if parts else ""
    clock = next((part for part in parts[1:] if ":" in part), "00:00")
    try:
        moment = datetime.datetime.fromisoformat(f"{day}T{clock}:00+00:00")
    except ValueError:
        return ""
    return moment.isoformat()


@dataclasses.dataclass(frozen=True)
class Episode:
    id: str
    question: str
    answer: str
    question_type: str
    question_date: str
    sessions: tuple[Session, ...]
    evidence_session_ids: tuple[str, ...]

    def is_abstention(self) -> bool:
        return self.id.endswith(ABSTENTION_MARKER)


def load(path: pathlib.Path, sessions_per_episode: int | None = None) -> list[Episode]:
    raw = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    return [_episode(entry, sessions_per_episode) for entry in raw]


def trim(source: pathlib.Path, target: pathlib.Path, sessions_per_episode: int) -> int:
    """Bound the haystack once, on disk, so every arm replays the identical corpus."""
    raw = json.loads(pathlib.Path(source).read_text(encoding="utf-8"))
    trimmed = [_trim_entry(entry, sessions_per_episode) for entry in raw]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(trimmed), encoding="utf-8")
    return len(trimmed)


def _trim_entry(entry: dict, keep: int) -> dict:
    evidence = set(entry.get(KEY_EVIDENCE) or [])
    ids = entry[KEY_SESSION_IDS]
    dates = entry[KEY_DATES]
    sessions = entry[KEY_SESSIONS]
    order = sorted(range(len(ids)), key=lambda index: (ids[index] not in evidence, index))[:keep]
    order.sort()
    picked = {
        KEY_SESSION_IDS: [ids[index] for index in order],
        KEY_DATES: [dates[index] for index in order],
        KEY_SESSIONS: [sessions[index] for index in order],
    }
    return {key: value for key, value in entry.items() if key not in picked} | picked


def _episode(entry: dict, keep: int | None) -> Episode:
    trimmed = _trim_entry(entry, keep) if keep else entry
    sessions = tuple(
        Session(
            id=str(session_id),
            date=str(date),
            turns=tuple(
                Turn(role=str(turn[KEY_ROLE]), content=str(turn[KEY_CONTENT])) for turn in turns
            ),
        )
        for session_id, date, turns in zip(
            trimmed[KEY_SESSION_IDS], trimmed[KEY_DATES], trimmed[KEY_SESSIONS], strict=False
        )
    )
    return Episode(
        id=str(trimmed[KEY_QUESTION_ID]),
        question=str(trimmed[KEY_QUESTION]),
        answer=str(trimmed[KEY_ANSWER]),
        question_type=str(trimmed[KEY_QUESTION_TYPE]),
        question_date=str(trimmed.get(KEY_QUESTION_DATE, "")),
        sessions=sessions,
        evidence_session_ids=tuple(str(item) for item in (trimmed.get(KEY_EVIDENCE) or [])),
    )
