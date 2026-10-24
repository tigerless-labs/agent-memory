"""The judgement half of a sleep, borrowed rather than owned (ADR-002).

Merging two entries, or writing an abstract that reads well, needs a reader; deciding *which*
entries are worth a second look does not. So the deterministic pass drafts, this module puts
the draft into words and reads the answer back, and something outside the core — a host agent,
or a model endpoint — supplies the reading. The core still contains no LLM client: a reasoner
is any callable that takes text and returns text.  The review request and outcome below are the
boundary shared by that compatibility path and native tool execution; neither grants mutation
authority.

The reply is a grammar, not a conversation. Anything that does not parse as a verdict on an
open proposal is discarded, so a reasoner that rambles, hallucinates an identifier, or is
steered by something written inside a memory can only ever fail to decide — never decide
something that was not on the table.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import time
from collections.abc import Sequence
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from . import prompts
from .record import MemoryRecord

if TYPE_CHECKING:
    from .manage_toolkit import ManageReviewToolkit
    from .toolkit import WriteToolkit

VERDICT_ACCEPT = "accept"
VERDICT_REJECT = "reject"
FENCE = "```"
FIELD_PROPOSAL = "proposal"
FIELD_VERDICT = "verdict"
FIELD_TEXT = "text"
FIELD_ABSTRACT = "abstract"
FIELD_BODY = "body"
FIELD_PARTS = "parts"
FIELD_PROVENANCE = "provenance"
PROPOSAL_MERGE = "merge"
PROPOSAL_SUPERSEDE = "supersede"
PROPOSAL_SPLIT = "split"
PROPOSAL_DELETE = "delete"
PROPOSAL_ABSTRACT_REVIEW = "abstract-review"


class Reasoner(Protocol):
    def __call__(self, prompt: str) -> str: ...


@runtime_checkable
class ToolReasoner(Protocol):
    """A standard tool-use agent: it calls the toolkit until it decides it is done."""

    def __call__(self, prompt: str) -> str: ...

    def converse(self, instructions: str, material: str, toolkit: WriteToolkit) -> None: ...


@runtime_checkable
class ManageToolReasoner(Protocol):
    """A Host-owned native loop over the strictly scoped Manage review toolkit."""

    def review_converse(
        self, instructions: str, material: str, toolkit: ManageReviewToolkit
    ) -> ReviewRuntime: ...


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
class Part:
    """One piece of a split: the knowledge itself plus the evidence it keeps."""

    abstract: str
    body: str
    provenance: tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True)
class Verdict:
    proposal_id: str
    accept: bool
    text: str = ""
    abstract: str = ""
    body: str = ""
    parts: tuple[Part, ...] = ()


@dataclasses.dataclass(frozen=True)
class ReviewSource:
    """One immutable evidence snapshot named by a proposal."""

    name: str
    source_hash: str
    type: str
    abstract: str
    body: str
    provenance: tuple[str, ...]
    valid_from: str | None = None
    memory_created_at: str | None = None
    memory_updated_at: str | None = None

    def as_dict(self, *, include_body: bool = False) -> dict[str, object]:
        return {
            "name": self.name,
            "source_hash": self.source_hash,
            "type": self.type,
            "abstract": self.abstract,
            **({"body": self.body} if include_body else {}),
            "provenance": list(self.provenance),
            "valid_from": self.valid_from,
            "memory_created_at": self.memory_created_at,
            "memory_updated_at": self.memory_updated_at,
        }


@dataclasses.dataclass(frozen=True)
class ReviewProposal:
    """A proposal plus the exact source versions the reviewer is allowed to inspect."""

    id: str
    kind: str
    targets: tuple[str, ...]
    reason: str
    evidence: str
    sources: tuple[ReviewSource, ...]

    def as_dict(self, *, include_body: bool = False) -> dict[str, object]:
        return {
            "id": self.id,
            "kind": self.kind,
            "targets": list(self.targets),
            "reason": self.reason,
            "evidence": self.evidence,
            "sources": [source.as_dict(include_body=include_body) for source in self.sources],
        }


@dataclasses.dataclass(frozen=True)
class ReviewLimits:
    """Library-owned bounds for one short-lived review run."""

    max_steps: int
    max_tool_calls: int
    timeout_seconds: float
    tool_result_chars: int
    evidence_chars: int
    raw_session_evidence: bool = False


@dataclasses.dataclass(frozen=True)
class ReviewRequest:
    """The complete, run-scoped input contract for proposal review."""

    proposals: tuple[ReviewProposal, ...]
    sources: tuple[ReviewSource, ...]
    limits: ReviewLimits


@dataclasses.dataclass(frozen=True)
class ReviewOutcome:
    """Transport-neutral output; only Manage may turn its verdicts into decisions."""

    verdicts: tuple[Verdict, ...]
    submitted: bool
    complete: bool
    mode: str = "text"
    rounds: int = 1
    tool_calls: int = 0
    duration_seconds: float = 0.0
    startup_seconds: float | None = None
    model_wait_seconds: float | None = None
    mcp_seconds: float | None = None
    shutdown_seconds: float | None = None
    apply_seconds: float = 0.0
    model_requests: int | None = None
    agent_turns: int | None = None
    input_tokens: int | None = None
    cached_input_tokens: int | None = None
    output_tokens: int | None = None
    evidence_reads: tuple[tuple[str, str], ...] = ()
    provenance_reads: tuple[tuple[str, str, str], ...] = ()
    tool_trace: tuple[tuple[str, bool], ...] = ()
    error: str = ""


@dataclasses.dataclass(frozen=True)
class ReviewRuntime:
    duration_seconds: float
    startup_seconds: float | None = None
    model_wait_seconds: float | None = None
    mcp_seconds: float | None = None
    shutdown_seconds: float | None = None
    model_requests: int | None = None
    agent_turns: int | None = None
    input_tokens: int | None = None
    cached_input_tokens: int | None = None
    output_tokens: int | None = None


def prepare(
    proposals: Sequence[Draft], records: Sequence[MemoryRecord], limits: ReviewLimits
) -> ReviewRequest:
    """Freeze the proposal menu and its allowed evidence before external reasoning starts."""
    named = {name for proposal in proposals for name in proposal.targets}
    scoped_sources = tuple(_source(record) for record in records if record.name in named)
    by_name = {source.name: source for source in scoped_sources}
    reviewed = []
    for proposal in proposals:
        proposal_sources = []
        for name in proposal.targets:
            source = by_name.get(name)
            if source is None:
                continue
            proposal_sources.append(source)
        reviewed.append(
            ReviewProposal(
                id=proposal.id,
                kind=proposal.kind,
                targets=proposal.targets,
                reason=proposal.reason,
                evidence=proposal.evidence,
                sources=tuple(proposal_sources),
            )
        )
    return ReviewRequest(tuple(reviewed), scoped_sources, limits)


def review_text(request: ReviewRequest, reasoner: Reasoner) -> ReviewOutcome:
    """Compatibility implementation: one prompt in, line-oriented verdicts out."""
    started = time.monotonic()
    reply = reasoner(render(request))
    verdicts = tuple(parse(reply))
    return ReviewOutcome(
        verdicts=verdicts,
        submitted=bool(verdicts),
        complete=bool(verdicts),
        mode="text",
        duration_seconds=time.monotonic() - started,
        model_requests=1,
        agent_turns=1,
    )


def native_instructions() -> str:
    return prompts.MANAGE_NATIVE_REVIEW


def native_material(request: ReviewRequest) -> str:
    """Send proposal summaries first; bodies remain behind scoped, observable reads."""
    proposals = [proposal.as_dict() for proposal in request.proposals]
    return json.dumps(
        {
            "proposals": proposals,
            "raw_session_evidence": request.limits.raw_session_evidence,
        },
        sort_keys=True,
    )


def render(
    request_or_proposals: ReviewRequest | Sequence[Draft],
    records: Sequence[MemoryRecord] | None = None,
) -> str:
    """Render the legacy full-evidence prompt.

    The two-argument form remains for callers outside Manage while the one-argument form consumes
    the shared review request used by both execution modes.
    """
    if isinstance(request_or_proposals, ReviewRequest):
        review_proposals: Sequence[Draft] = request_or_proposals.proposals
        review_sources: Sequence[ReviewSource] = request_or_proposals.sources
    else:
        review_proposals = request_or_proposals
        named = {name for proposal in review_proposals for name in proposal.targets}
        review_sources = [_source(record) for record in (records or ()) if record.name in named]
    lines = [
        f"- {proposal.id} ({proposal.kind}): {', '.join(proposal.targets)} — "
        f"{proposal.reason} [{proposal.evidence}]"
        for proposal in review_proposals
    ]
    entries = [
        (
            f"### {source.name}\n"
            f"type: {source.type}\n"
            f"abstract: {source.abstract}\n"
            f"valid_from: {source.valid_from or 'unknown'}\n"
            f"memory_created_at: {source.memory_created_at or 'unknown'}\n"
            f"memory_updated_at: {source.memory_updated_at or 'unknown'}\n\n"
            f"{source.body.strip()}"
        )
        for source in review_sources
    ]
    return prompts.manage_review(
        proposals="## proposals\n\n" + "\n".join(lines),
        entries="## entries\n\n" + "\n\n".join(entries),
    )


def _source(record: MemoryRecord) -> ReviewSource:
    return ReviewSource(
        name=record.name,
        source_hash=record.source_hash
        or hashlib.sha256(record.to_text().encode("utf-8")).hexdigest(),
        type=record.type,
        abstract=record.abstract,
        body=record.body,
        provenance=tuple(record.provenance),
        valid_from=record.valid_from or None,
        memory_created_at=record.created or None,
        memory_updated_at=record.updated or None,
    )


def parse(reply: str) -> list[Verdict]:
    verdicts: list[Verdict] = []
    for line in reply.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith(FENCE):
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        verdict = verdict_from_payload(payload)
        if verdict is not None:
            verdicts.append(verdict)
    return verdicts


def verdict_from_payload(payload: object) -> Verdict | None:
    """Decode one typed verdict without granting it authority over a proposal."""
    if not isinstance(payload, dict):
        return None
    proposal_id = payload.get(FIELD_PROPOSAL)
    verdict = payload.get(FIELD_VERDICT)
    if not isinstance(proposal_id, str) or verdict not in (VERDICT_ACCEPT, VERDICT_REJECT):
        return None
    return Verdict(
        proposal_id=proposal_id,
        accept=verdict == VERDICT_ACCEPT,
        text=_string(payload.get(FIELD_TEXT)),
        abstract=_string(payload.get(FIELD_ABSTRACT)),
        body=_string(payload.get(FIELD_BODY)),
        parts=_parts(payload.get(FIELD_PARTS)),
    )


def verdict_as_dict(verdict: Verdict) -> dict[str, object]:
    return {
        FIELD_PROPOSAL: verdict.proposal_id,
        FIELD_VERDICT: VERDICT_ACCEPT if verdict.accept else VERDICT_REJECT,
        **({FIELD_TEXT: verdict.text} if verdict.text else {}),
        **({FIELD_ABSTRACT: verdict.abstract} if verdict.abstract else {}),
        **({FIELD_BODY: verdict.body} if verdict.body else {}),
        **(
            {
                FIELD_PARTS: [
                    {
                        FIELD_ABSTRACT: part.abstract,
                        FIELD_BODY: part.body,
                        FIELD_PROVENANCE: list(part.provenance),
                    }
                    for part in verdict.parts
                ]
            }
            if verdict.parts
            else {}
        ),
    }


def _string(value: object) -> str:
    return value if isinstance(value, str) else ""


def _parts(raw: object) -> tuple[Part, ...]:
    if not isinstance(raw, list):
        return ()
    parts = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        provenance = item.get(FIELD_PROVENANCE)
        parts.append(
            Part(
                abstract=_string(item.get(FIELD_ABSTRACT)),
                body=_string(item.get(FIELD_BODY)),
                provenance=tuple(str(p) for p in provenance)
                if isinstance(provenance, list)
                else (),
            )
        )
    return tuple(parts)
