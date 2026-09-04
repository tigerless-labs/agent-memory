"""Sleep-time consolidation, value-based forgetting, tree evolution.

The layer everything else exists to make possible. Nobody approves a sleep (Invariant 6):
the deterministic half tidies dates, weight, links and directories; the judged half — merge,
split, supersede, delete — is ruled by a reasoner that can only choose from the menu the core
drafted, is capped per kind per sleep, and never removes a file. Every sleep leaves a report,
and a git commit when the store lives in a repository, so a wrong call is visible and
reversible from outside the loop.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import pathlib
import re
import subprocess

from . import reasoning, timestamp
from . import record as record_module
from .access_log import KIND_READ, AccessLog
from .clock import Clock
from .database import Database
from .errors import FieldError, MemoryStoreError, NotFoundError, ValidationError
from .ledger import LEDGER_FILENAME, VERDICT_ACCEPTED, VERDICT_REJECTED, Decision, DecisionLedger
from .pending import Pending
from .record import DATE_FIELDS, MemoryRecord
from .sessions import Pointer, parse_pointer
from .store import Store

PROPOSAL_MERGE = "merge"
PROPOSAL_SUPERSEDE = "supersede"
PROPOSAL_SPLIT = "split"
PROPOSAL_DELETE = "delete"
PROPOSAL_ABSTRACT_REVIEW = "abstract-review"

ACTION_DATE_NORMALISED = "date-normalised"
ACTION_DUPLICATE_MERGED = "duplicate-merged"
ACTION_LINK_ADDED = "link-added"
ACTION_WEIGHT_SETTLED = "weight-settled"
ACTION_CLUSTERED = "clustered"
ACTION_GROUP_MERGED = "group-merged"
ACTION_REDISTILL_REQUESTED = "redistill-requested"

PROPOSAL_ID_LENGTH = 12
REPORT_SUFFIX = ".md"
MERGED_SUFFIX = "-merged"
SECTION_PREFIX = "## "
GIT = "git"
_WORDS = re.compile(r"[0-9a-z]+")
_STOPWORDS = frozenset(
    {"the", "a", "an", "and", "or", "of", "to", "is", "are", "for", "in", "on", "with", "that"}
)
_PLURAL = "s"


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
    actions: tuple[Action, ...]
    proposals: tuple[Proposal, ...]
    inspected: int
    path: str = ""
    decisions: tuple[Decision, ...] = ()
    withheld: tuple[str, ...] = ()
    committed: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "at": self.at,
            "inspected": self.inspected,
            "actions": [action.as_dict() for action in self.actions],
            "proposals": [proposal.as_dict() for proposal in self.proposals],
            "decisions": [decision.as_dict() for decision in self.decisions],
            "withheld": list(self.withheld),
            "committed": self.committed,
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

    def sleep(self, reasoner: reasoning.Reasoner | None = None) -> DreamReport:
        records = self._store.records()
        hits, reads, last_access = self._usage()

        actions: list[Action] = []
        actions.extend(self._normalise_dates(records))
        actions.extend(self._settle_weights(records, reads, last_access))
        actions.extend(self._add_cooccurrence_links(records))
        actions.extend(self._merge_exact_duplicates(records))
        actions.extend(self._merge_near_duplicate_groups())
        actions.extend(self._cluster(self._store.records()))
        actions.extend(self._request_redistill(self._store.records()))

        records = self._store.records()
        proposals = self.proposals(records=records, hits=hits)
        decisions, withheld = self._review(proposals, records, reasoner)
        settled = {decision.proposal_id for decision in decisions}

        report = DreamReport(
            at=self._clock.now().isoformat(),
            actions=tuple(actions),
            proposals=tuple(p for p in proposals if p.id not in settled),
            inspected=len(records),
            decisions=decisions,
            withheld=withheld,
        )
        report = dataclasses.replace(report, path=str(self._write_report(report)))
        return dataclasses.replace(report, committed=self._commit(report))

    def _review(
        self,
        proposals: list[Proposal],
        records: list[MemoryRecord],
        reasoner: reasoning.Reasoner | None,
    ) -> tuple[tuple[Decision, ...], tuple[str, ...]]:
        """A reasoner may refuse anything and accept up to the per-kind cap; a verdict on
        something that is not open, or that an earlier verdict invalidated, is dropped."""
        if reasoner is None or not proposals:
            return (), ()
        open_now = {proposal.id: proposal for proposal in proposals}
        caps = self._caps()
        accepted: dict[str, int] = {}
        decisions: list[Decision] = []
        withheld: list[str] = []
        for verdict in reasoning.parse(reasoner(reasoning.render(proposals, records))):
            proposal = open_now.get(verdict.proposal_id)
            if proposal is None:
                continue
            if verdict.accept and accepted.get(proposal.kind, 0) >= caps.get(proposal.kind, 0):
                withheld.append(proposal.id)
                continue
            try:
                decisions.append(self.decide(proposal.id, accept=verdict.accept, verdict=verdict))
            except MemoryStoreError:
                withheld.append(proposal.id)
                continue
            if verdict.accept:
                accepted[proposal.kind] = accepted.get(proposal.kind, 0) + 1
        return tuple(decisions), tuple(withheld)

    def _caps(self) -> dict[str, int]:
        manage = self._config.manage
        return {
            PROPOSAL_MERGE: manage.max_merges_per_sleep,
            PROPOSAL_SUPERSEDE: manage.max_supersedes_per_sleep,
            PROPOSAL_SPLIT: manage.max_splits_per_sleep,
            PROPOSAL_DELETE: manage.max_deletes_per_sleep,
            PROPOSAL_ABSTRACT_REVIEW: len(self._store.records()),
        }

    def proposals(
        self, records: list[MemoryRecord] | None = None, hits: dict[str, int] | None = None
    ) -> list[Proposal]:
        """Everything worth a ruling that nobody has ruled on yet. Pure: nothing is written."""
        inspected = self._store.records() if records is None else records
        counts = self._usage()[0] if hits is None else hits
        decided = self._ledger().decided()
        drafted: list[Proposal] = []
        drafted.extend(self._propose_merges(inspected))
        drafted.extend(self._propose_splits(inspected))
        drafted.extend(self._propose_abstract_review(inspected))
        drafted.extend(self._propose_deletions(inspected, counts))
        return [proposal for proposal in drafted if proposal.id not in decided]

    def decide(
        self,
        proposal_id: str,
        accept: bool,
        text: str = "",
        verdict: reasoning.Verdict | None = None,
    ) -> Decision:
        """Rule on one proposal. Acceptance applies it through the write path."""
        proposal = self._open(proposal_id)
        content = verdict or reasoning.Verdict(proposal_id, accept, text=text)
        detail = self._apply(proposal, content) if accept else ""
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

    def _apply(self, proposal: Proposal, verdict: reasoning.Verdict) -> str:
        if proposal.kind == PROPOSAL_MERGE:
            return self._merge(proposal, verdict)
        if proposal.kind == PROPOSAL_SUPERSEDE:
            return self._supersede(proposal)
        if proposal.kind == PROPOSAL_SPLIT:
            return self._split(proposal, verdict)
        if proposal.kind == PROPOSAL_DELETE:
            return self._delete(proposal)
        return self._rewrite_abstract(proposal, verdict.text)

    def _merge(self, proposal: Proposal, verdict: reasoning.Verdict) -> str:
        """The reasoner writes the knowledge; the library computes time, identity, evidence."""
        if not verdict.abstract.strip() or not verdict.body.strip():
            raise ValidationError(
                [FieldError("body", "accepting a merge needs the merged abstract and body")]
            )
        entries = [self._entry(name) for name in proposal.targets]
        keeper = max(entries, key=lambda record: (len(record.body), record.created, record.name))
        name = keeper.name + MERGED_SUFFIX
        if self._store.find(name) is not None:
            name += "-" + self._clock.stamp().lower()
        now = self._clock.timestamp()
        links = sorted(
            {link for record in entries for link in record.links} - {r.name for r in entries}
        )
        merged = self._store.record(
            type=keeper.type,
            name=name,
            fields=dict(keeper.fields),
            abstract=verdict.abstract.strip(),
            body=verdict.body.strip(),
            links=links,
            weight=max(record.weight for record in entries),
            valid_from=now,
            provenance=[pointer for record in entries for pointer in record.provenance],
            create_group=True,
        )
        for record in entries:
            record_module.invalidate(record, merged.valid_from or now, merged.name)
            record.updated = now
            self._rewrite(record)
        return f"merged into {merged.name}"

    def _supersede(self, proposal: Proposal) -> str:
        entries = [self._entry(name) for name in proposal.targets]
        keeper = max(entries, key=lambda record: (len(record.body), record.created, record.name))
        now = self._clock.timestamp()
        for record in entries:
            if record.name == keeper.name:
                continue
            record_module.invalidate(record, now, keeper.name)
            record.updated = now
            self._rewrite(record)
        return f"kept {keeper.name}"

    def _split(self, proposal: Proposal, verdict: reasoning.Verdict) -> str:
        """The original keeps its name as the first part; every other part is a new file."""
        parts = [part for part in verdict.parts if part.abstract.strip() and part.body.strip()]
        if len(parts) < len(("first", "second")):
            raise ValidationError(
                [FieldError("parts", "accepting a split needs at least two parts with content")]
            )
        original = self._entry(proposal.targets[0])
        own = set(original.provenance)
        now = self._clock.timestamp()
        names = []
        for index, part in enumerate(parts):
            provenance = [pointer for pointer in part.provenance if pointer in own] or list(own)
            if index == 0:
                original.abstract = part.abstract.strip()
                original.body = part.body.strip()
                original.provenance = provenance
                original.updated = now
                self._rewrite(original)
                names.append(original.name)
                continue
            written = self._store.record(
                type=original.type,
                name=f"{original.name}-{index}",
                fields=dict(original.fields),
                abstract=part.abstract.strip(),
                body=part.body.strip(),
                links=list(original.links),
                weight=original.weight,
                valid_from=original.valid_from,
                provenance=provenance,
                create_group=True,
            )
            names.append(written.name)
        return "split into " + ", ".join(names)

    def _delete(self, proposal: Proposal) -> str:
        removed = self._store.delete(proposal.targets[0])
        return f"marked {removed.name} invalid"

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
            wanted = {field: _as_instant(getattr(record, field)) for field in DATE_FIELDS}
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
            actions.append(Action(ACTION_DATE_NORMALISED, record.name, ", ".join(sorted(changed))))
        return actions

    def _settle_weights(
        self, records: list[MemoryRecord], reads: dict[str, int], last_access: dict[str, str]
    ) -> list[Action]:
        actions: list[Action] = []
        now = self._clock.now()
        for record in records:
            before = record.weight
            after = before + self._config.weight.boost_step * min(
                reads.get(record.name, 0), self._config.manage.max_boosts_per_sleep
            )
            if self._idle_days(record, last_access, now) >= self._config.weight.decay_after_days:
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
            record_module.invalidate(record, self._clock.timestamp(), original.name)
            self._rewrite(record)
            actions.append(Action(ACTION_DUPLICATE_MERGED, record.name, original.name))
        return actions

    def _merge_near_duplicate_groups(self) -> list[Action]:
        """Two group directories that differ only in spelling are one topic split in two."""
        actions: list[Action] = []
        layout = self._store.layout
        for schema in self._store.schemas.all():
            if not schema.group:
                continue
            by_key: dict[str, list[str]] = {}
            for group in sorted(layout.groups_of(schema.type)):
                by_key.setdefault(_group_key(group), []).append(group)
            for variants in by_key.values():
                if len(variants) < len(("one", "other")):
                    continue
                keeper = max(
                    variants, key=lambda group: (self._group_size(schema.type, group), group)
                )
                for group in variants:
                    if group == keeper:
                        continue
                    for record in self._store.records():
                        if record.type == schema.type and record.fields.get(schema.group) == group:
                            self._move(record, schema.group, keeper)
                            actions.append(
                                Action(ACTION_GROUP_MERGED, record.name, f"{group} -> {keeper}")
                            )
                    self._prune_empty_groups()
        return actions

    def _cluster(self, records: list[MemoryRecord]) -> list[Action]:
        """A directory holding many files that share vocabulary is a topic without a name yet;
        naming it is a directory operation, so it happens without a ruling."""
        actions: list[Action] = []
        by_parent: dict[pathlib.Path, list[MemoryRecord]] = {}
        for record in records:
            if record.is_active() and record.path is not None:
                by_parent.setdefault(record.path.parent, []).append(record)
        for _, flat in sorted(by_parent.items()):
            buckets: dict[str, set[str]] = {}
            for record in flat:
                for token in _tokens(f"{record.name} {record.abstract}"):
                    buckets.setdefault(token, set()).add(record.name)
            groups: dict[frozenset[str], set[str]] = {}
            for token, names in buckets.items():
                if len(names) < self._config.manage.cluster_min_files:
                    continue
                groups.setdefault(frozenset(names), set()).add(token)
            known = {record.name: record for record in flat}
            for grouped, shared in sorted(groups.items(), key=lambda group: sorted(group[0])):
                if len(shared) < self._config.manage.cluster_min_shared_tokens:
                    continue
                label = "-".join(sorted(shared))[: self._config.storage.slug_max_length]
                movable = []
                for name in sorted(grouped):
                    schema = self._store.schema_of(known[name])
                    group_field = schema.group if schema is not None else None
                    if not schema or not group_field:
                        continue
                    if known[name].fields.get(group_field, "") == label:
                        continue
                    if label in self._store.layout.groups_of(schema.type):
                        continue
                    movable.append((known[name], group_field))
                for record, group_field in movable:
                    current = record.fields.get(group_field, "")
                    self._move(record, group_field, label)
                    actions.append(Action(ACTION_CLUSTERED, record.name, f"{current} -> {label}"))
                self._prune_empty_groups()
        return actions

    def _prune_empty_groups(self) -> None:
        for schema in self._store.schemas.all():
            for group in self._store.layout.groups_of(schema.type):
                folder = self._store.layout.type_dir(schema.type) / group
                if not any(folder.iterdir()):
                    folder.rmdir()

    def _request_redistill(self, records: list[MemoryRecord]) -> list[Action]:
        """Raw material hit again and again with no memory citing it was missed by the still."""
        with self._database.connect() as connection:
            counts = AccessLog(connection).counts()
        cited = [
            pointer
            for record in records
            for pointer in (parse_pointer(item) for item in record.provenance)
            if pointer is not None
        ]
        queue = Pending(self._store.layout)
        actions: list[Action] = []
        for name, hits in sorted(counts.items()):
            pointer = parse_pointer(name)
            if pointer is None or hits < self._config.manage.raw_hit_min:
                continue
            if any(pointer.overlaps(known) for known in cited):
                continue
            if queue.request_redistill(pointer):
                actions.append(Action(ACTION_REDISTILL_REQUESTED, name, f"hits={hits}"))
        return actions

    def _move(self, record: MemoryRecord, group_field: str, group: str) -> MemoryRecord:
        """A move is a write with one field changed; name, body and evidence travel intact."""
        return self._store.record(
            type=record.type,
            name=record.name,
            fields={**record.fields, group_field: group},
            abstract=record.abstract,
            body=record.body,
            links=list(record.links),
            weight=record.weight,
            valid_from=record.valid_from,
            author=record.author,
            create_group=True,
        )

    def _group_size(self, type_name: str, group: str) -> int:
        folder = self._store.layout.type_dir(type_name) / group
        return len(list(folder.glob("*.md"))) if folder.is_dir() else 0

    def _propose_merges(self, records: list[MemoryRecord]) -> list[Proposal]:
        """Two entries saying one thing: supersede when one already holds the other, merge
        when each holds something the other lacks and one file could hold both."""
        active = [record for record in records if record.is_active()]
        proposals: list[Proposal] = []
        for index, left in enumerate(active):
            for right in active[index + 1 :]:
                overlap = _similarity(left, right)
                if overlap < self._config.manage.merge_proposal_similarity:
                    continue
                first, second = _tokens(left.abstract), _tokens(right.abstract)
                if first <= second or second <= first:
                    kind = PROPOSAL_SUPERSEDE
                elif left.type == right.type:
                    kind = PROPOSAL_MERGE
                else:
                    continue
                proposals.append(
                    Proposal(
                        kind=kind,
                        targets=(left.name, right.name),
                        reason="abstracts overlap above the proposal threshold",
                        evidence=f"similarity={overlap:.2f}",
                    )
                )
        return proposals

    def _propose_splits(self, records: list[MemoryRecord]) -> list[Proposal]:
        """A file with several sections drawn from several conversations will go stale in
        pieces, and a file is the invalidation atom (Invariant 7)."""
        minimum = self._config.manage.split_min_sections
        proposals: list[Proposal] = []
        for record in records:
            if not record.is_active():
                continue
            sections = sum(
                1 for line in record.body.splitlines() if line.startswith(SECTION_PREFIX)
            )
            sessions = {
                pointer.session
                for pointer in (parse_pointer(item) for item in record.provenance)
                if pointer is not None
            }
            if sections >= minimum and len(sessions) >= len(("one", "other")):
                proposals.append(
                    Proposal(
                        kind=PROPOSAL_SPLIT,
                        targets=(record.name,),
                        reason="one file holds parts that will expire separately",
                        evidence=f"sections={sections}, sessions={len(sessions)}",
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

    def _propose_deletions(
        self, records: list[MemoryRecord], hits: dict[str, int]
    ) -> list[Proposal]:
        return [
            Proposal(
                kind=PROPOSAL_DELETE,
                targets=(record.name,),
                reason="never recalled and already at the weight floor",
                evidence=f"weight={record.weight:.2f}",
            )
            for record in records
            if record.is_active()
            and hits.get(record.name, 0) == 0
            and record.weight <= self._config.weight.floor
        ]

    def _idle_days(
        self, record: MemoryRecord, last_access: dict[str, str], now: dt.datetime
    ) -> float:
        stamp = last_access.get(record.name) or record.updated
        try:
            seen = timestamp.parse(stamp)
        except ValueError:
            seen = timestamp.parse(record.updated)
        return timestamp.days_between(now, seen)

    def _rewrite(self, record: MemoryRecord) -> None:
        self._store.write(record)

    def _write_report(self, report: DreamReport) -> str:
        folder = self._store.layout.dream_reports
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / (self._clock.stamp() + REPORT_SUFFIX)
        lines = [
            f"# dream report {report.at}",
            "",
            f"inspected: {report.inspected}",
            "",
            "## applied",
            "",
        ]
        lines.extend(
            f"- {action.kind}: {action.target} — {action.detail}" for action in report.actions
        )
        lines.extend(["", "## decided", ""])
        lines.extend(
            f"- {decision.proposal_id} {decision.verdict} — {decision.detail}"
            for decision in report.decisions
        )
        lines.extend(["", "## proposals (open)", ""])
        lines.extend(
            f"- {proposal.kind}: {', '.join(proposal.targets)} — {proposal.reason}"
            f" ({proposal.evidence})"
            for proposal in report.proposals
        )
        if report.withheld:
            lines.extend(["", "## withheld (over the cap or refused by the write path)", ""])
            lines.extend(f"- {proposal_id}" for proposal_id in report.withheld)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return str(path)

    def _commit(self, report: DreamReport) -> bool:
        """One sleep, one commit: the audit trail a human reviews from outside the loop."""
        if not self._config.manage.git_commit:
            return False
        root = str(self._store.root)
        try:
            inside = subprocess.run(
                [GIT, "-C", root, "rev-parse", "--is-inside-work-tree"],
                capture_output=True,
                text=True,
                check=False,
            )
            if inside.returncode != 0 or inside.stdout.strip() != "true":
                return False
            subprocess.run(
                [GIT, "-C", root, "add", "-A", "--", root], check=True, capture_output=True
            )
            done = subprocess.run(
                [GIT, "-C", root, "commit", "-q", "-m", f"sleep {report.at}", "--", root],
                capture_output=True,
                text=True,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return done.returncode == 0

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


def _group_key(group: str) -> str:
    key = "".join(_WORDS.findall(group.lower()))
    return key[: -len(_PLURAL)] if key.endswith(_PLURAL) and len(key) > len(_PLURAL) else key


def _as_instant(value: str | None) -> str:
    if not value:
        return ""
    try:
        return timestamp.canonical(value)
    except ValueError:
        return ""


def _overlapping(pointer: Pointer, cited: list[Pointer]) -> bool:
    return any(pointer.overlaps(known) for known in cited)


SECONDS_PER_HOUR = 3600.0
STAMP_FORMAT = "%Y%m%dT%H%M%S%f"
