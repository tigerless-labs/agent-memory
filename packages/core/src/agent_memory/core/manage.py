"""Sleep-time consolidation, value-based forgetting, tree evolution.

The layer everything else exists to make possible. Its authority is graded (Invariant 6):
unattended work only adds or amends, anything that loses a distinction becomes a proposal,
and physical removal is never reachable from here at all.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import re

from .access_log import KIND_READ, AccessLog
from .clock import Clock
from .database import Database
from .errors import AuthorityError, FieldError, NotFoundError, ValidationError
from .ledger import LEDGER_FILENAME, VERDICT_ACCEPTED, VERDICT_REJECTED, Decision, DecisionLedger
from .record import STATUS_ACTIVE, STATUS_STALE, MemoryRecord
from .store import Store

TIER_UNATTENDED = "T0"
TIER_PROPOSAL = "T1"
TIER_HUMAN = "T2"

PROPOSAL_MERGE = "merge"
PROPOSAL_SUPERSEDE = "supersede"
PROPOSAL_CLUSTER = "cluster"
PROPOSAL_ABSTRACT_REVIEW = "abstract-review"
PROPOSAL_DEMOTE = "demote"

ACTION_DATE_NORMALISED = "date-normalised"
ACTION_DUPLICATE_MERGED = "duplicate-merged"
ACTION_STALENESS_MARKED = "staleness-marked"
ACTION_LINK_ADDED = "link-added"
ACTION_WEIGHT_SETTLED = "weight-settled"

PROPOSALS_HUMAN_ONLY = frozenset({PROPOSAL_CLUSTER})
PROPOSALS_SUPERSEDING = frozenset({PROPOSAL_MERGE, PROPOSAL_SUPERSEDE})
PROPOSAL_ID_LENGTH = 12
REPORT_SUFFIX = ".md"
_WORDS = re.compile(r"[0-9a-z]+")
_STOPWORDS = frozenset(
    {"the", "a", "an", "and", "or", "of", "to", "is", "are", "for", "in", "on", "with", "that"}
)


@dataclasses.dataclass(frozen=True)
class Proposal:
    kind: str
    targets: tuple[str, ...]
    reason: str
    evidence: str = ""

    @property
    def id(self) -> str:
        material = self.kind + "|" + "|".join(sorted(self.targets))
        return hashlib.sha256(material.encode("utf-8")).hexdigest()[:PROPOSAL_ID_LENGTH]

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "kind": self.kind,
            "targets": list(self.targets),
            "reason": self.reason,
            "evidence": self.evidence,
        }


@dataclasses.dataclass(frozen=True)
class Action:
    kind: str
    target: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "target": self.target, "detail": self.detail}


@dataclasses.dataclass(frozen=True)
class DreamReport:
    at: str
    tier: str
    actions: tuple[Action, ...]
    proposals: tuple[Proposal, ...]
    inspected: int
    path: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "at": self.at,
            "tier": self.tier,
            "inspected": self.inspected,
            "actions": [action.as_dict() for action in self.actions],
            "proposals": [proposal.as_dict() for proposal in self.proposals],
            "path": self.path,
        }


class Manage:
    def __init__(self, store: Store, clock: Clock | None = None):
        self._store = store
        self._config = store.config
        self._clock = clock or store.clock
        self._database = Database(store.layout)

    def due(self, sessions_since: int) -> bool:
        last = self._last_sleep()
        if last is None:
            return sessions_since >= self._config.manage.trigger_min_sessions
        elapsed_hours = (self._clock.now() - last).total_seconds() / SECONDS_PER_HOUR
        return (
            elapsed_hours >= self._config.manage.trigger_min_hours
            and sessions_since >= self._config.manage.trigger_min_sessions
        )

    def sleep(self) -> DreamReport:
        records = self._store.records()
        hits, reads, last_access = self._usage()

        actions: list[Action] = []
        actions.extend(self._normalise_dates(records))
        actions.extend(self._settle_weights(records, reads, last_access))
        actions.extend(self._mark_staleness(records, last_access))
        actions.extend(self._add_cooccurrence_links(records))
        actions.extend(self._merge_exact_duplicates(records))

        proposals = self.proposals(records=records, hits=hits)

        report = DreamReport(
            at=self._clock.now().isoformat(),
            tier=TIER_UNATTENDED,
            actions=tuple(actions),
            proposals=tuple(proposals),
            inspected=len(records),
        )
        return dataclasses.replace(report, path=str(self._write_report(report)))

    def proposals(
        self, records: list[MemoryRecord] | None = None, hits: dict[str, int] | None = None
    ) -> list[Proposal]:
        """Everything worth confirming that nobody has ruled on yet. Pure: nothing is written."""
        inspected = self._store.records() if records is None else records
        counts = self._usage()[0] if hits is None else hits
        decided = self._ledger().decided()
        drafted: list[Proposal] = []
        drafted.extend(self._propose_merges(inspected))
        drafted.extend(self._propose_abstract_review(inspected))
        drafted.extend(self._propose_demotions(inspected, counts))
        drafted.extend(self._propose_clusters(inspected))
        return [proposal for proposal in drafted if proposal.id not in decided]

    def decide(self, proposal_id: str, accept: bool, text: str = "") -> Decision:
        """Confirm or refuse one proposal. Acceptance applies it through the write path."""
        proposal = self._open(proposal_id)
        detail = ""
        if accept:
            detail = self._apply(proposal, text)
        return self._ledger().append(
            Decision(
                proposal_id=proposal.id,
                verdict=VERDICT_ACCEPTED if accept else VERDICT_REJECTED,
                at=self._clock.now().isoformat(),
                detail=detail,
            )
        )

    def _open(self, proposal_id: str) -> Proposal:
        for proposal in self.proposals():
            if proposal.id == proposal_id:
                return proposal
        raise NotFoundError(f"no open proposal {proposal_id}")

    def _apply(self, proposal: Proposal, text: str) -> str:
        if proposal.kind in PROPOSALS_HUMAN_ONLY:
            raise AuthorityError(
                f"{proposal.kind} moves files between directories and stays {TIER_HUMAN}"
            )
        if proposal.kind in PROPOSALS_SUPERSEDING:
            return self._supersede(proposal)
        if proposal.kind == PROPOSAL_DEMOTE:
            return self._demote(proposal)
        return self._rewrite_abstract(proposal, text)

    def _supersede(self, proposal: Proposal) -> str:
        entries = [self._entry(name) for name in proposal.targets]
        keeper = max(entries, key=lambda record: (len(record.body), record.created, record.name))
        for record in entries:
            if record.name == keeper.name:
                continue
            record.superseded_by = keeper.name
            self._rewrite(record)
        return f"kept {keeper.name}"

    def _demote(self, proposal: Proposal) -> str:
        record = self._entry(proposal.targets[0])
        before = record.weight
        record.weight = max(
            self._config.weight.floor, before - self._config.weight.demote_penalty
        )
        self._rewrite(record)
        return f"{before:.2f} -> {record.weight:.2f}"

    def _rewrite_abstract(self, proposal: Proposal, text: str) -> str:
        if not text.strip():
            raise ValidationError(
                [FieldError("text", "accepting an abstract review needs the replacement abstract")]
            )
        record = self._entry(proposal.targets[0])
        record.abstract = text.strip()
        self._rewrite(record)
        return f"rewrote the abstract of {record.name}"

    def _entry(self, name: str) -> MemoryRecord:
        record = self._store.find(name)
        if record is None:
            raise NotFoundError(f"no memory named {name}")
        return record

    def _ledger(self) -> DecisionLedger:
        return DecisionLedger(self._store.layout.dream_reports / LEDGER_FILENAME)

    def _usage(self) -> tuple[dict[str, int], dict[str, int], dict[str, str]]:
        """Lifetime counts decide what was never useful; only new reads earn weight, so one
        read is settled once however many sleeps follow it."""
        since = self._last_sleep()
        with self._database.connect() as connection:
            log = AccessLog(connection)
            hits = log.counts()
            last_access = log.last_access()
            query = "SELECT name, COUNT(*) AS hits FROM access_log WHERE kind = ?"
            parameters: tuple[object, ...] = (KIND_READ,)
            if since is not None:
                query += " AND at > ?"
                parameters += (since.isoformat(),)
            reads = {
                str(row["name"]): int(row["hits"])
                for row in connection.execute(query + " GROUP BY name", parameters)
            }
        return hits, reads, last_access

    def _normalise_dates(self, records: list[MemoryRecord]) -> list[Action]:
        actions: list[Action] = []
        for record in records:
            wanted = {field: _as_date_string(getattr(record, field)) for field in DATE_FIELDS}
            changed = {
                field: value
                for field, value in wanted.items()
                if value and value != getattr(record, field)
            }
            if not changed:
                continue
            for field, value in changed.items():
                setattr(record, field, value)
            self._rewrite(record)
            actions.append(
                Action(ACTION_DATE_NORMALISED, record.name, ", ".join(sorted(changed)))
            )
        return actions

    def _settle_weights(
        self, records: list[MemoryRecord], reads: dict[str, int], last_access: dict[str, str]
    ) -> list[Action]:
        actions: list[Action] = []
        today = self._clock.now().date()
        for record in records:
            before = record.weight
            after = before + self._config.weight.boost_step * min(
                reads.get(record.name, 0), self._config.manage.max_boosts_per_sleep
            )
            if self._idle_days(record, last_access, today) >= self._config.weight.decay_after_days:
                after -= self._config.weight.decay_step
            after = min(self._config.weight.ceiling, max(self._config.weight.floor, after))
            if after == before:
                continue
            record.weight = after
            self._rewrite(record)
            actions.append(
                Action(ACTION_WEIGHT_SETTLED, record.name, f"{before:.2f} -> {after:.2f}")
            )
        return actions

    def _mark_staleness(
        self, records: list[MemoryRecord], last_access: dict[str, str]
    ) -> list[Action]:
        actions: list[Action] = []
        today = self._clock.now().date()
        for record in records:
            if record.status != STATUS_ACTIVE:
                continue
            if self._idle_days(record, last_access, today) < self._config.manage.stale_after_days:
                continue
            record.status = STATUS_STALE
            self._rewrite(record)
            actions.append(Action(ACTION_STALENESS_MARKED, record.name, "idle beyond threshold"))
        return actions

    def _add_cooccurrence_links(self, records: list[MemoryRecord]) -> list[Action]:
        with self._database.connect() as connection:
            rows = connection.execute(
                "SELECT query, name FROM access_log WHERE query != ''"
            ).fetchall()
        together: dict[tuple[str, str], int] = {}
        by_query: dict[str, set[str]] = {}
        for row in rows:
            by_query.setdefault(str(row["query"]), set()).add(str(row["name"]))
        for names in by_query.values():
            for left in names:
                for right in names:
                    if left < right:
                        together[(left, right)] = together.get((left, right), 0) + 1

        known = {record.name: record for record in records}
        actions: list[Action] = []
        for (left, right), count in sorted(together.items()):
            if count < self._config.manage.link_cooccurrence_min:
                continue
            for source, target in ((left, right), (right, left)):
                record = known.get(source)
                if record is None or target not in known or target in record.links:
                    continue
                record.links.append(target)
                self._rewrite(record)
                actions.append(Action(ACTION_LINK_ADDED, source, target))
        return actions

    def _merge_exact_duplicates(self, records: list[MemoryRecord]) -> list[Action]:
        seen: dict[str, MemoryRecord] = {}
        actions: list[Action] = []
        for record in sorted(records, key=lambda item: (item.created, item.name)):
            if not record.is_active():
                continue
            key = _fingerprint(record)
            original = seen.get(key)
            if original is None:
                seen[key] = record
                continue
            record.superseded_by = original.name
            self._rewrite(record)
            actions.append(Action(ACTION_DUPLICATE_MERGED, record.name, original.name))
        return actions

    def _propose_merges(self, records: list[MemoryRecord]) -> list[Proposal]:
        active = [record for record in records if record.is_active()]
        proposals: list[Proposal] = []
        for index, left in enumerate(active):
            for right in active[index + 1 :]:
                overlap = _similarity(left, right)
                if overlap < self._config.manage.merge_proposal_similarity:
                    continue
                kind = PROPOSAL_SUPERSEDE if left.type == right.type else PROPOSAL_MERGE
                proposals.append(
                    Proposal(
                        kind=kind,
                        targets=(left.name, right.name),
                        reason="abstracts overlap above the proposal threshold",
                        evidence=f"similarity={overlap:.2f}",
                    )
                )
        return proposals

    def _propose_abstract_review(self, records: list[MemoryRecord]) -> list[Proposal]:
        limit = self._config.storage.abstract_max_chars
        return [
            Proposal(
                kind=PROPOSAL_ABSTRACT_REVIEW,
                targets=(record.name,),
                reason="abstract is too thin to recognise this memory by",
                evidence=f"words={len(_tokens(record.abstract))}",
            )
            for record in records
            if record.is_active()
            and (
                len(_tokens(record.abstract)) < self._config.manage.abstract_min_words
                or len(record.abstract) > limit
            )
        ]

    def _propose_demotions(
        self, records: list[MemoryRecord], hits: dict[str, int]
    ) -> list[Proposal]:
        return [
            Proposal(
                kind=PROPOSAL_DEMOTE,
                targets=(record.name,),
                reason="never recalled and already at the retrieval floor",
                evidence=f"weight={record.weight:.2f}",
            )
            for record in records
            if record.is_active()
            and hits.get(record.name, 0) == 0
            and record.weight <= self._config.recall.retrieval_weight_floor
        ]

    def _propose_clusters(self, records: list[MemoryRecord]) -> list[Proposal]:
        proposals: list[Proposal] = []
        for domain in self._config.storage.domains:
            flat = [
                record
                for record in records
                if record.domain == domain
                and record.is_active()
                and record.path is not None
                and record.path.parent == self._store.layout.domain_dir(domain)
            ]
            buckets: dict[str, set[str]] = {}
            for record in flat:
                for token in _tokens(f"{record.name} {record.abstract}"):
                    buckets.setdefault(token, set()).add(record.name)
            groups: dict[frozenset[str], set[str]] = {}
            for token, names in buckets.items():
                if len(names) < self._config.manage.cluster_min_files:
                    continue
                groups.setdefault(frozenset(names), set()).add(token)
            for names, shared in sorted(groups.items(), key=lambda group: sorted(group[0])):
                if len(shared) < self._config.manage.cluster_min_shared_tokens:
                    continue
                proposals.append(
                    Proposal(
                        kind=PROPOSAL_CLUSTER,
                        targets=tuple(sorted(names)),
                        reason=f"{domain} root holds a topic worth its own directory",
                        evidence=f"shared {', '.join(sorted(shared))} across {len(names)} files",
                    )
                )
        return proposals

    def _idle_days(
        self, record: MemoryRecord, last_access: dict[str, str], today: dt.date
    ) -> float:
        stamp = last_access.get(record.name) or record.updated
        try:
            seen = dt.datetime.fromisoformat(stamp).date()
        except ValueError:
            seen = dt.date.fromisoformat(record.updated)
        return float((today - seen).days)

    def _rewrite(self, record: MemoryRecord) -> None:
        self._store.write(record)

    def _write_report(self, report: DreamReport) -> str:
        folder = self._store.layout.dream_reports
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / (self._clock.stamp() + REPORT_SUFFIX)
        lines = [
            f"# dream report {report.at}",
            "",
            f"tier: {report.tier}",
            f"inspected: {report.inspected}",
            "",
            "## applied",
            "",
        ]
        lines.extend(
            f"- {action.kind}: {action.target} — {action.detail}" for action in report.actions
        )
        lines.extend(["", "## proposals (awaiting confirmation)", ""])
        lines.extend(
            f"- {proposal.kind}: {', '.join(proposal.targets)} — {proposal.reason}"
            f" ({proposal.evidence})"
            for proposal in report.proposals
        )
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return str(path)

    def _last_sleep(self) -> dt.datetime | None:
        folder = self._store.layout.dream_reports
        reports = sorted(folder.glob("*" + REPORT_SUFFIX)) if folder.exists() else []
        for path in reversed(reports):
            try:
                return dt.datetime.strptime(path.stem, STAMP_FORMAT).replace(tzinfo=dt.UTC)
            except ValueError:
                continue
        return None


def _tokens(text: str) -> set[str]:
    return {word for word in _WORDS.findall(text.lower()) if word not in _STOPWORDS}


def _similarity(left: MemoryRecord, right: MemoryRecord) -> float:
    first = _tokens(left.abstract)
    second = _tokens(right.abstract)
    if not first or not second:
        return 0.0
    return len(first & second) / len(first | second)


def _fingerprint(record: MemoryRecord) -> str:
    return " ".join(sorted(_tokens(record.abstract))) + "|" + " ".join(sorted(_tokens(record.body)))


def _as_date_string(value: str | None) -> str:
    if not value:
        return ""
    try:
        return dt.date.fromisoformat(value).isoformat()
    except ValueError:
        pass
    try:
        return dt.datetime.fromisoformat(value).date().isoformat()
    except ValueError:
        return ""


DATE_FIELDS = ("created", "updated", "valid_from")
SECONDS_PER_HOUR = 3600.0
STAMP_FORMAT = "%Y%m%dT%H%M%S%f"
