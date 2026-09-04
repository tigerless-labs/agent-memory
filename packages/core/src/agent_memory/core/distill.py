"""One boundary, end to end: batch, render, reconcile, ask, apply, repair, advance.

The asking is a callable — text in, text out — supplied from outside the core (Invariant 5).
Everything around it is deterministic: what the executor sees, what its reply may do, and
where a write that fails goes.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable

from . import batching, pending, prompts, reconcile, render
from .errors import FieldError
from .sessions import Message, Pointer, render_pointer
from .store import BatchResult, Rejected, Store
from .watermark import Watermark

Ask = Callable[[str], str]


@dataclasses.dataclass(frozen=True)
class BatchReport:
    pointer: str
    written: tuple[str, ...]
    rejected: tuple[str, ...]
    pending: int

    def as_dict(self) -> dict[str, object]:
        return {
            "pointer": self.pointer,
            "written": list(self.written),
            "rejected": list(self.rejected),
            "pending": self.pending,
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


def distill(store: Store, session: str, messages: list[Message], ask: Ask) -> DistillReport:
    config = store.config.write
    watermark = Watermark(store.layout, store.clock)
    queue = pending.Pending(store.layout)
    reports: list[BatchReport] = []
    distilled = watermark.read(session).distilled
    for batch in batching.batches(messages, config.max_distill_input_chars):
        sheet = reconcile.build(store, session, batch)
        prompt = prompts.distill_sheet(
            prompts.slot_table(sheet.slots),
            sheet.render(),
            render.conversation(batch),
            slot_table=config.slot_table,
            event_lane=config.event_lane,
        )
        specs, errors = reconcile.parse_operations(ask(prompt))
        specs = queue.drain(session) + specs
        result, leftovers = _apply(store, sheet, specs, errors)
        for _ in range(config.repair_rounds):
            if not leftovers:
                break
            reply = ask(prompts.repair(sheet.render(), _describe(leftovers)))
            retry, errors = reconcile.parse_operations(reply)
            if not retry:
                break
            result_more, leftovers = _apply(store, sheet, retry, errors)
            result = BatchResult(
                written=result.written + result_more.written, rejected=result_more.rejected
            )
        queued = queue.append(session, [spec for spec, _ in leftovers])
        distilled = max(distilled, batch[-1].index + 1)
        watermark.settle(session, distilled)
        reports.append(
            BatchReport(
                pointer=render_pointer(sheet.pointer),
                written=tuple(record.name for record in result.written),
                rejected=tuple(str(item.errors) for item in result.rejected),
                pending=queued,
            )
        )
    return DistillReport(session=session, batches=tuple(reports), consumed=distilled)


def _apply(
    store: Store,
    sheet: reconcile.Sheet,
    specs: list[dict[str, object]],
    parse_errors: list[FieldError],
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
