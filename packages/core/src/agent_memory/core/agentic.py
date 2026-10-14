"""The negotiation between the library and its executor, one round at a time.

Each round the executor either asks for a tool — a search of the store, or one memory in
full — or hands back the operations. The library runs the tool, appends what it saw to the
transcript, and asks again, up to a cap. The executor decides; the library executes, so the
core still holds no model client (Invariant 5). A handle a tool returned is as good as one
the sheet carried; a handle nobody has seen stays refused.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Callable

from . import prompts, reconcile
from .config import WriteConfig
from .errors import FieldError
from .reasoning import ReasonerRun
from .recall import Recall
from .store import Store

TOOL_RECALL = "recall"
TOOL_READ = "read"
TOOLS = (TOOL_RECALL, TOOL_READ)
KEY_TOOL = "look"
KEY_QUERY = "query"
KEY_NAME = "name"
FENCE = "```"
EXTENSION_ROUNDS = 1
FORMAT_RETRIES = 1

Ask = "Callable[[str], str]"


@dataclasses.dataclass(frozen=True)
class Outcome:
    specs: list[dict[str, object]]
    errors: list[FieldError]
    sheet: reconcile.Sheet
    rounds: int
    transcript: str


def negotiate(
    store: Store, sheet: reconcile.Sheet, opening: str, ask, config: WriteConfig
) -> Outcome:
    begin = getattr(ask, "begin", None)
    run = begin(_opening(opening)) if callable(begin) else None
    try:
        return _negotiate(store, sheet, opening, ask, config, run)
    finally:
        if run is not None:
            run.close()


def _negotiate(
    store: Store,
    sheet: reconcile.Sheet,
    opening: str,
    ask: Callable[[str], str],
    config: WriteConfig,
    run: ReasonerRun | None,
) -> Outcome:
    transcript: list[str] = []
    incremental = ""
    budget = config.max_rounds
    extended = 0
    retried = 0
    rounds = 0
    while rounds < budget:
        rounds += 1
        last = rounds >= budget
        if run is None:
            reply = ask(_render(opening, transcript, last))
        else:
            reply = run.step(_increment(incremental, last))
        calls, lines = _split(reply)
        if not calls:
            specs, errors = reconcile.parse_operations("\n".join(lines))
            if not specs and retried < FORMAT_RETRIES:
                retried += 1
                budget += 1
                incremental = prompts.format_retry(reply)
                transcript.append(incremental)
                continue
            if not specs and not errors:
                errors = [FieldError("response", "executor returned no final operations")]
            return Outcome(specs, errors, sheet, rounds, "\n\n".join(transcript))
        observations = []
        for call in calls:
            observation, sheet = _run(store, sheet, call, config)
            observations.append(observation)
        rendered_observations = "\n\n".join(observations)
        transcript.append(prompts.tool_round(reply, rendered_observations))
        incremental = prompts.tool_observations(rendered_observations)
        if last and extended < EXTENSION_ROUNDS:
            extended += 1
            budget += 1
    return Outcome(
        [],
        [FieldError("rounds", "executor exhausted rounds without final operations")],
        sheet,
        rounds,
        "\n\n".join(transcript),
    )


def _render(opening: str, transcript: list[str], last: bool) -> str:
    parts = [_opening(opening)]
    parts.extend(transcript)
    if last:
        parts.append(prompts.FINAL_ROUND)
    return "\n\n".join(parts)


def _opening(opening: str) -> str:
    return "\n\n".join((opening, prompts.TOOL_RULES))


def _increment(prompt: str, last: bool) -> str:
    parts = [prompt] if prompt else []
    if last:
        parts.append(prompts.FINAL_ROUND)
    return "\n\n".join(parts)


def _split(reply: str) -> tuple[list[dict[str, object]], list[str]]:
    calls: list[dict[str, object]] = []
    others: list[str] = []
    for line in reply.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(FENCE):
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            others.append(line)
            continue
        if isinstance(payload, dict) and KEY_TOOL in payload:
            calls.append(payload)
        else:
            others.append(line)
    return calls, others


def _run(
    store: Store, sheet: reconcile.Sheet, call: dict[str, object], config: WriteConfig
) -> tuple[str, reconcile.Sheet]:
    tool = str(call.get(KEY_TOOL) or "")
    if tool == TOOL_RECALL:
        query = str(call.get(KEY_QUERY) or "").strip()
        if not query:
            return prompts.observation(tool, "recall needs a query"), sheet
        hits = Recall(store).recall(query, limit=config.reconcile_entries, log=False)
        found = tuple(
            reconcile.Handle(hit.name, hit.type, hit.status, hit.updated, hit.abstract)
            for hit in hits
        )
        text = "\n".join(handle.render() for handle in found) or "(nothing found)"
        return prompts.observation(tool, _clip(text, config)), _extend(sheet, found)
    if tool == TOOL_READ:
        name = str(call.get(KEY_NAME) or "").strip()
        record = store.find(name) if name else None
        if record is None or not record.is_active():
            return prompts.observation(tool, f"no active memory named {name}"), sheet
        handle = reconcile.Handle(
            record.name, record.type, record.status, record.valid_from or "", record.abstract
        )
        text = f"{handle.render()}\n\n{record.body.strip()}"
        return prompts.observation(tool, _clip(text, config)), _extend(sheet, (handle,))
    return prompts.observation(tool, f"unknown tool; the tools are {', '.join(TOOLS)}"), sheet


def _extend(sheet: reconcile.Sheet, found: tuple[reconcile.Handle, ...]) -> reconcile.Sheet:
    known = sheet.handle_names()
    fresh = tuple(handle for handle in found if handle.name not in known)
    if not fresh:
        return sheet
    return dataclasses.replace(sheet, handles=sheet.handles + fresh)


def _clip(text: str, config: WriteConfig) -> str:
    limit = config.tool_result_chars
    return text if len(text) <= limit else text[:limit] + "\n(truncated)"
