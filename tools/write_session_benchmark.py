"""Bounded paired benchmark for Codex Write session reuse.

This intentionally forces the library-owned Recall -> Read -> SUPERSEDE path so a one-turn
answer cannot be mistaken for evidence of multi-round reuse. It creates fresh isolated stores
for every arm and caps each Host invocation at one attempt.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import pathlib
import tempfile
import time

from agent_memory.core import distill, sessions
from agent_memory.core.store import Store
from agent_memory.executor.hosts import HOST_CODEX, Host, HostResult, HostSpec
from agent_memory.executor.reasoners import HostReasoner, StatefulHostReasoner

MODEL = "gpt-5.6-sol"
SESSION = "write-session-benchmark"
OLD_NAME = "deployment-window"
ARCHIVE = [
    "user: Effective 2026-10-13, the agent-memory deployment window moves from Friday at "
    "21:00 UTC to Saturday at 22:30 UTC. Keep the rollback checklist unchanged."
]
PROTOCOL = (
    """## Reproducible benchmark protocol

For this benchmark, use the library tools in exactly three model replies even if the reconcile
sheet already contains the handle:
1. Reply only with {"look":"recall","query":"agent-memory deployment window"}.
2. After the recall observation, reply only with {"look":"read","name":"deployment-window"}.
3. After the read observation, reply only with this final operation:
"""
    '{"type":"fact","op":"supersede","handle":"deployment-window",'
    '"fields":{"project":"agent-memory","subject":"deployment window Saturday"},'
    '"abstract":"The agent-memory deployment window is Saturday at 22:30 UTC",'
    '"body":"Effective 2026-10-13, the deployment window moved from Friday at 21:00 UTC '
    'to Saturday at 22:30 UTC. The rollback checklist remains unchanged.",'
    '"valid_from":"2026-10-13","provenance":["0"]}'
    """
Do not skip either library look and do not call Host tools."""
)


class CountingHost:
    """Records the exact Host boundary without changing transport behavior."""

    def __init__(self, host: Host):
        self.host = host
        self.name = host.name
        self.prompts: list[str] = []
        self.results: list[HostResult] = []
        self.session_homes: list[pathlib.Path] = []

    def run(self, prompt: str, **kwargs) -> HostResult:
        self.prompts.append(prompt)
        result = self.host.run(prompt, **kwargs)
        self.results.append(result)
        return result

    def run_session(self, prompt: str, **kwargs) -> HostResult:
        self.prompts.append(prompt)
        result = self.host.run_session(prompt, **kwargs)
        self.results.append(result)
        return result

    def isolated_codex_environment(
        self, extra: dict[str, str], scratch: pathlib.Path
    ) -> dict[str, str]:
        environment = self.host.isolated_codex_environment(extra, scratch)
        self.session_homes.append(pathlib.Path(environment["CODEX_HOME"]))
        return environment


@dataclasses.dataclass
class GuidedReasoner:
    reasoner: HostReasoner | StatefulHostReasoner

    def __call__(self, prompt: str) -> str:
        return self.reasoner(prompt + "\n\n" + PROTOCOL)

    def begin(self, opening: str):
        begin = getattr(self.reasoner, "begin", None)
        if not callable(begin):
            raise AttributeError("stateless reasoner has no session")
        return begin(opening + "\n\n" + PROTOCOL)


@dataclasses.dataclass
class StatelessGuidedReasoner:
    reasoner: HostReasoner

    def __call__(self, prompt: str) -> str:
        return self.reasoner(prompt + "\n\n" + PROTOCOL)


def _deltas(values: list[int | None], cumulative: bool) -> list[int | None]:
    if not cumulative:
        return values
    previous = 0
    result: list[int | None] = []
    for value in values:
        if value is None:
            result.append(None)
            continue
        result.append(value - previous)
        previous = value
    return result


def _arm(mode: str, pair: int) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix=f"agent-memory-{mode}-{pair}-") as root:
        store = Store(pathlib.Path(root) / "store", agent="write-session-benchmark")
        store.init()
        store.config.write.repair_rounds = 0
        store.record(
            name=OLD_NAME,
            type="fact",
            fields={"project": "agent-memory", "subject": "deployment window"},
            abstract="The agent-memory deployment window is Friday at 21:00 UTC",
            body="The deployment window is Friday at 21:00 UTC. Keep the rollback checklist.",
            valid_from="2026-01-01",
        )
        pointer = store.archive.append_session(SESSION, ARCHIVE)
        messages = sessions.resolve(store.layout, pointer)
        host = CountingHost(
            Host(
                HostSpec(
                    name=HOST_CODEX,
                    binary="codex",
                    model=MODEL,
                    attempts=1,
                    timeout_seconds=300.0,
                )
            )
        )
        if mode == "stateful":
            ask = GuidedReasoner(StatefulHostReasoner(host))
        else:
            ask = StatelessGuidedReasoner(HostReasoner(host))
        started = time.monotonic()
        report = distill.distill(store, SESSION, messages, ask)
        elapsed = time.monotonic() - started
        written = [name for batch in report.batches for name in batch.written]
        records = [store.find(name) for name in written]
        replies = [result.text for result in host.results]
        input_tokens = [result.input_tokens for result in host.results]
        cached_input_tokens = [result.cached_input_tokens for result in host.results]
        final_usage = host.results[-1] if host.results else None
        return {
            "pair": pair,
            "mode": mode,
            "wall_seconds": round(elapsed, 3),
            "batch_seconds": [round(elapsed, 3)],
            "agent_rounds": sum(batch.rounds for batch in report.batches),
            "cli_process_starts": len(host.results),
            "reasoner_calls": len(host.results),
            "reasoner_seconds_by_call": [round(result.seconds, 3) for result in host.results],
            "prompt_chars": sum(len(prompt) for prompt in host.prompts),
            "prompt_chars_by_call": [len(prompt) for prompt in host.prompts],
            "input_tokens_by_call": input_tokens,
            "input_tokens_incremental_by_call": _deltas(
                input_tokens, cumulative=mode == "stateful"
            ),
            "cached_input_tokens_by_call": cached_input_tokens,
            "cached_input_tokens_incremental_by_call": _deltas(
                cached_input_tokens, cumulative=mode == "stateful"
            ),
            "output_tokens_by_call": [result.output_tokens for result in host.results],
            "input_tokens_cumulative": final_usage.input_tokens if final_usage else None,
            "cached_input_tokens_cumulative": (
                final_usage.cached_input_tokens if final_usage else None
            ),
            "recall_calls": sum('"look":"recall"' in reply.replace(" ", "") for reply in replies),
            "read_calls": sum('"look":"read"' in reply.replace(" ", "") for reply in replies),
            "written": written,
            "rejected": [item for batch in report.batches for item in batch.rejected],
            "pending": sum(batch.pending for batch in report.batches),
            "provenance_valid": bool(records)
            and all(record is not None and record.provenance for record in records),
            "old_superseded": not store.find(OLD_NAME).is_active(),
            "session_ids": [result.session_id or None for result in host.results],
            "session_home_released": all(not path.exists() for path in host.session_homes),
            "errors": [result.error for result in host.results if not result.ok],
            "replies": replies,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=1, choices=range(1, 6))
    parser.add_argument("--out", type=pathlib.Path)
    args = parser.parse_args()
    results: list[dict[str, object]] = []
    for pair in range(1, args.runs + 1):
        order = ("stateless", "stateful") if pair % 2 else ("stateful", "stateless")
        for mode in order:
            result = _arm(mode, pair)
            results.append(result)
            print(json.dumps(result, sort_keys=True), flush=True)
    payload = {
        "model": MODEL,
        "scenario": "forced Recall -> Read -> SUPERSEDE",
        "runs": args.runs,
        "results": results,
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
