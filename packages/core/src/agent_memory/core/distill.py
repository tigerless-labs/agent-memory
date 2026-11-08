"""One boundary, end to end: batch, render, reconcile, ask, apply, repair, advance.

The asking is a callable — text in, text out — supplied from outside the core (Invariant 5).
Everything around it is deterministic: what the executor sees, what its reply may do, and
where a write that fails goes.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable

from . import agentic, batching, pending, prompts, reconcile, render
from .errors import FieldError, ValidationError
from .locking import file_lock
from .sessions import Message, Pointer, render_pointer
from .store import BatchResult, Rejected, Store
from .watermark import Watermark
from .write_trace import WriteTrace

Ask = Callable[[str], str]


@dataclasses.dataclass(frozen=True)
class BatchReport:
    pointer: str
    written: tuple[str, ...]
    rejected: tuple[str, ...]
    pending: int
    rounds: int = 1

    def as_dict(self) -> dict[str, object]:
        return {
            "pointer": self.pointer,
            "written": list(self.written),
            "rejected": list(self.rejected),
            "pending": self.pending,
            "rounds": self.rounds,
        }


@dataclasses.dataclass(frozen=True)
class DistillReport:
    session: str
    batches: tuple[BatchReport, ...]
    consumed: int

    def as_dict(self) -> dict[str, object]:
        return {
            "session": self.session,
            "batches": [batch.as_dict() for batch in self.batches],
            "consumed": self.consumed,
        }


def distill(
    store: Store,
    session: str,
    messages: list[Message],
    ask: Ask,
    trace: WriteTrace | None = None,
) -> DistillReport:
    config = store.config.write
    watermark = Watermark(store.layout, store.clock)
    queue = pending.Pending(store.layout)
    reports: list[BatchReport] = []
    distilled = watermark.read(session).distilled
    for batch in batching.batches(messages, config.max_distill_input_chars):
        sheet = reconcile.build(store, session, batch)
        if trace is not None:
            trace.batch(
                render_pointer(sheet.pointer),
                sum(len(message.text) for message in batch),
                len(sheet.slots),
            )
        brief = prompts.distill_brief(
            prompts.slot_table(sheet.slots),
            sheet.render(),
            render.conversation(batch),
            slot_table=config.slot_table,
            event_lane=config.event_lane,
        )
        outcome = agentic.negotiate(store, sheet, brief, ask, config, trace=trace)
        if outcome.errors:
            raise ValidationError(outcome.errors)
        sheet = outcome.sheet
        specs, errors = outcome.specs, outcome.errors
        specs = queue.drain(session) + specs
        result, leftovers = _apply(store, sheet, specs, errors, trace)
        for number in range(1, config.repair_rounds + 1):
            if not leftovers:
                break
            if trace is not None:
                trace.repair(number, len(leftovers))
            reply = ask(prompts.repair(sheet.render(), _describe(leftovers)))
            retry, errors = reconcile.parse_operations(reply)
            if not retry:
                break
            result_more, leftovers = _apply(store, sheet, retry, errors, trace)
            result = BatchResult(
                written=result.written + result_more.written, rejected=result_more.rejected
            )
        queued = queue.append(session, [spec for spec, _ in leftovers])
        distilled = max(distilled, batch[-1].index + 1)
        with file_lock(
            store.layout.capture_lock,
            timeout=store.config.storage.lock_timeout_seconds,
        ):
            watermark.settle(session, distilled)
        reports.append(
            BatchReport(
                pointer=render_pointer(sheet.pointer),
                written=tuple(record.name for record in result.written),
                rejected=tuple(str(item.errors) for item in result.rejected),
                pending=queued,
                rounds=outcome.rounds,
            )
        )
    return DistillReport(session=session, batches=tuple(reports), consumed=distilled)


def _apply(
    store: Store,
    sheet: reconcile.Sheet,
    specs: list[dict[str, object]],
    parse_errors: list[FieldError],
    trace: WriteTrace | None = None,
) -> tuple[BatchResult, list[tuple[dict[str, object], list[FieldError]]]]:
    leftovers: list[tuple[dict[str, object], list[FieldError]]] = []
    accepted: list[dict[str, object]] = []
    origins: list[dict[str, object]] = []
    for spec in specs:
        problems = reconcile.check(spec, sheet)
        if problems:
            leftovers.append((spec, problems))
            continue
        record_spec = reconcile.to_record_spec(spec, sheet)
        if record_spec is None:
            continue
        accepted.append(record_spec)
        origins.append(spec)
    result = store.record_many(accepted) if accepted else BatchResult(written=[], rejected=[])
    for item in result.rejected:
        leftovers.append((origins[item.index], list(item.errors)))
    if parse_errors:
        leftovers.append(({"raw": "unparsed lines"}, parse_errors))
    if trace is not None:
        trace.operations(
            [record.name for record in result.written],
            [
                {
                    "operation": reconcile.operation_of(origins[item.index]),
                    "errors": [error.as_dict() for error in item.errors],
                }
                for item in result.rejected
            ],
        )
    return result, [(spec, errors) for spec, errors in leftovers if "raw" not in spec]


def _describe(leftovers: list[tuple[dict[str, object], list[FieldError]]]) -> str:
    lines = []
    for spec, errors in leftovers:
        reasons = "; ".join(f"{error.field}: {error.reason}" for error in errors)
        lines.append(f"- {spec} -> {reasons}")
    return "\n".join(lines)


def pointer_of(messages: list[Message], session: str) -> Pointer:
    return Pointer(session, messages[0].index, messages[-1].index)


__all__ = ["Ask", "BatchReport", "DistillReport", "Rejected", "distill", "pointer_of"]
