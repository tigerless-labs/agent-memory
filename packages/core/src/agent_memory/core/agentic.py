"""The negotiation between the library and its executor over one batch.

A tool reasoner is a standard tool-use agent: it receives the instructions and the batch
apart, calls the Write toolkit as often as it judges useful, and answers by submitting
operations. A text reasoner keeps the line protocol: each round it either asks for a look
or hands back operations as plain text, and the library runs the look through the same
toolkit. Either way the executor decides and the library executes, so the core still holds
no model client (Invariant 5).
"""

from __future__ import annotations

import dataclasses
import json

from . import prompts, reconcile, toolkit
from .config import WriteConfig
from .errors import FieldError
from .reasoning import ToolReasoner
from .store import Store

TOOL_RECALL = toolkit.TOOL_RECALL
TOOL_RECALL_WITH_EVIDENCE = toolkit.TOOL_RECALL_WITH_EVIDENCE
TOOL_READ = toolkit.TOOL_READ
TOOLS = (TOOL_RECALL, TOOL_RECALL_WITH_EVIDENCE, TOOL_READ)
KEY_TOOL = "look"
KEY_QUERY = toolkit.ARG_QUERY
KEY_NAME = toolkit.ARG_NAME
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
    store: Store, sheet: reconcile.Sheet, brief: prompts.Brief, ask, config: WriteConfig
) -> Outcome:
    kit = toolkit.WriteToolkit(store, sheet)
    if isinstance(ask, ToolReasoner):
        return _converse(kit, brief, ask, config)
    return _text_protocol(kit, brief.text_protocol(), ask, config)


def _converse(
    kit: toolkit.WriteToolkit, brief: prompts.Brief, ask: ToolReasoner, config: WriteConfig
) -> Outcome:
    ask.converse(
        brief.tool_system(config.recall_with_evidence_enabled), brief.material, kit
    )
    errors = (
        []
        if kit.submission is not None
        else [FieldError("response", "executor submitted no operations")]
    )
    return Outcome(list(kit.submission or []), errors, kit.sheet, len(kit.calls), kit.transcript())


def _text_protocol(kit: toolkit.WriteToolkit, opening: str, ask, config: WriteConfig) -> Outcome:
    transcript: list[str] = []
    budget = config.max_rounds
    extended = 0
    retried = 0
    rounds = 0
    while rounds < budget:
        rounds += 1
        last = rounds >= budget
        prompt = _render(
            opening,
            transcript,
            last,
            prompts.tool_rules(config.recall_with_evidence_enabled),
        )
        reply = ask(prompt)
        calls, lines = _split(reply)
        if not calls:
            specs, errors = reconcile.parse_operations("\n".join(lines))
            if not specs and retried < FORMAT_RETRIES:
                retried += 1
                budget += 1
                transcript.append(prompts.format_retry(reply))
                continue
            if not specs and not errors:
                errors = [FieldError("response", "executor returned no final operations")]
            return Outcome(specs, errors, kit.sheet, rounds, "\n\n".join(transcript))
        observations = [_look(kit, call, config) for call in calls]
        transcript.append(prompts.tool_round(reply, "\n\n".join(observations)))
        if last and extended < EXTENSION_ROUNDS:
            extended += 1
            budget += 1
    return Outcome(
        [],
        [FieldError("rounds", "executor exhausted rounds without final operations")],
        kit.sheet,
        rounds,
        "\n\n".join(transcript),
    )


def _render(opening: str, transcript: list[str], last: bool, tool_rules: str) -> str:
    parts = [opening, tool_rules]
    parts.extend(transcript)
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


def _look(kit: toolkit.WriteToolkit, call: dict[str, object], config: WriteConfig) -> str:
    tool = str(call.get(KEY_TOOL) or "")
    available = tuple(spec.name for spec in kit.catalogue() if spec.name != toolkit.TOOL_SUBMIT)
    if tool not in available:
        return prompts.observation(tool, f"unknown tool; the tools are {', '.join(available)}")
    arguments = {key: value for key, value in call.items() if key != KEY_TOOL}
    return prompts.observation(tool, _clip(kit.call(tool, arguments).text, config))


def _clip(text: str, config: WriteConfig) -> str:
    limit = config.tool_result_chars
    return text if len(text) <= limit else text[:limit] + "\n(truncated)"
