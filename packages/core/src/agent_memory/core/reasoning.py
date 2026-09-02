"""The judgement half of a sleep, borrowed rather than owned (ADR-002).

Merging two entries, or writing an abstract that reads well, needs a reader; deciding *which*
entries are worth a second look does not. So the deterministic pass drafts, this module puts
the draft into words and reads the answer back, and something outside the core — a host agent,
or a model endpoint — supplies the reading. The core still contains no LLM client: a reasoner
is any callable that takes text and returns text.

The reply is a grammar, not a conversation. Anything that does not parse as a verdict on an
open proposal is discarded, so a reasoner that rambles, hallucinates an identifier, or is
steered by something written inside a memory can only ever fail to decide — never decide
something that was not on the table.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Sequence
from typing import Protocol

from . import prompts
from .record import MemoryRecord

VERDICT_ACCEPT = "accept"
VERDICT_REJECT = "reject"
FENCE = "```"
FIELD_PROPOSAL = "proposal"
FIELD_VERDICT = "verdict"
FIELD_TEXT = "text"


class Reasoner(Protocol):
    def __call__(self, prompt: str) -> str: ...


class Draft(Protocol):
    """What a proposal looks like from here — enough to describe it, nothing to change it."""

    @property
    def id(self) -> str: ...

    @property
    def kind(self) -> str: ...

    @property
    def targets(self) -> tuple[str, ...]: ...

    @property
    def reason(self) -> str: ...

    @property
    def evidence(self) -> str: ...


@dataclasses.dataclass(frozen=True)
class Verdict:
    proposal_id: str
    accept: bool
    text: str = ""


def render(proposals: Sequence[Draft], records: Sequence[MemoryRecord]) -> str:
    named = {name for proposal in proposals for name in proposal.targets}
    lines = [
        f"- {proposal.id} ({proposal.kind}): {', '.join(proposal.targets)} — "
        f"{proposal.reason} [{proposal.evidence}]"
        for proposal in proposals
    ]
    entries = [
        f"### {record.name}\nabstract: {record.abstract}\n\n{record.body.strip()}"
        for record in records
        if record.name in named
    ]
    return prompts.manage_review(
        proposals="## proposals\n\n" + "\n".join(lines),
        entries="## entries\n\n" + "\n\n".join(entries),
    )


def parse(reply: str) -> list[Verdict]:
    verdicts: list[Verdict] = []
    for line in reply.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(FENCE):
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        proposal_id = payload.get(FIELD_PROPOSAL)
        verdict = payload.get(FIELD_VERDICT)
        if not isinstance(proposal_id, str) or verdict not in (VERDICT_ACCEPT, VERDICT_REJECT):
            continue
        text = payload.get(FIELD_TEXT)
        verdicts.append(
            Verdict(
                proposal_id=proposal_id,
                accept=verdict == VERDICT_ACCEPT,
                text=text if isinstance(text, str) else "",
            )
        )
    return verdicts
