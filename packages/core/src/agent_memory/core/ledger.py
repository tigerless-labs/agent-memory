"""Decisions taken on Manage proposals.

Truth, not cache: no memory file records that a human already refused a merge, so a rebuilt
index cannot bring the refusal back. The ledger is markdown beside the dream reports —
reviewable in a diff, and append-only, so a decision is never quietly revised.
"""

from __future__ import annotations

import dataclasses
import pathlib
import re

LEDGER_FILENAME = "decisions.md"
VERDICT_ACCEPTED = "accepted"
VERDICT_REJECTED = "rejected"
HEADING = "# proposal decisions"
_LINE = re.compile(
    r"^- (?P<id>\S+) (?P<verdict>accepted|rejected) (?P<at>\S+)(?: — (?P<detail>.*))?$"
)


@dataclasses.dataclass(frozen=True)
class Decision:
    proposal_id: str
    verdict: str
    at: str
    detail: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "proposal": self.proposal_id,
            "verdict": self.verdict,
            "at": self.at,
            "detail": self.detail,
        }

    def render(self) -> str:
        line = f"- {self.proposal_id} {self.verdict} {self.at}"
        return f"{line} — {self.detail}" if self.detail else line


class DecisionLedger:
    def __init__(self, path: pathlib.Path):
        self._path = path

    def decided(self) -> dict[str, Decision]:
        if not self._path.exists():
            return {}
        found: dict[str, Decision] = {}
        for raw in self._path.read_text(encoding="utf-8").splitlines():
            match = _LINE.match(raw.strip())
            if match is None:
                continue
            found[match["id"]] = Decision(
                proposal_id=match["id"],
                verdict=match["verdict"],
                at=match["at"],
                detail=match["detail"] or "",
            )
        return found

    def append(self, decision: Decision) -> Decision:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        head = self._path.read_text(encoding="utf-8") if self._path.exists() else HEADING + "\n\n"
        self._path.write_text(head + decision.render() + "\n", encoding="utf-8")
        return decision
