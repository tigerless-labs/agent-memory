"""Three-way Write benchmark including the batch-scoped Codex app-server mode."""

from __future__ import annotations

import argparse
import dataclasses
import json
import pathlib
import statistics
import tempfile
import time

import write_session_benchmark as baseline
from agent_memory.core import distill, sessions
from agent_memory.core.store import Store
from agent_memory.executor.app_server import APP_SERVER_ALLOWED_ITEMS
from agent_memory.executor.hosts import HOST_CODEX, Host, HostSpec
from agent_memory.executor.reasoners import AppServerHostReasoner, AppServerHostReasonerRun

APP_SERVER_MODE = "app-server"


@dataclasses.dataclass
class CountingAppServerRun:
    run: AppServerHostReasonerRun
    prompts: list[str] = dataclasses.field(default_factory=list)

    def step(self, prompt: str) -> str:
        self.prompts.append(
            self.run.opening + (("\n\n" + prompt) if prompt else "") if not self.prompts else prompt
        )
        return self.run.step(prompt)

    def close(self) -> None:
        self.run.close()


@dataclasses.dataclass
class CountingAppServerReasoner(AppServerHostReasoner):
    runs: list[CountingAppServerRun] = dataclasses.field(default_factory=list)

    def begin(self, opening: str) -> CountingAppServerRun:
        run = CountingAppServerRun(super().begin(opening))
        self.runs.append(run)
        return run


def app_server_arm(pair: int) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix=f"agent-memory-app-server-{pair}-") as root:
        store = Store(pathlib.Path(root) / "store", agent="write-session-benchmark")
        store.init()
        store.config.write.repair_rounds = 0
        store.record(
            name=baseline.OLD_NAME,
            type="fact",
            fields={"project": "agent-memory", "subject": "deployment window"},
            abstract="The agent-memory deployment window is Friday at 21:00 UTC",
            body="The deployment window is Friday at 21:00 UTC. Keep the rollback checklist.",
            valid_from="2026-01-01",
        )
        pointer = store.archive.append_session(baseline.SESSION, baseline.ARCHIVE)
        messages = sessions.resolve(store.layout, pointer)
        reasoner = CountingAppServerReasoner(
            Host(
                HostSpec(
                    name=HOST_CODEX,
                    binary="codex",
                    model=baseline.MODEL,
                    attempts=1,
                    timeout_seconds=300.0,
                )
            )
        )
        ask = baseline.GuidedReasoner(reasoner)  # type: ignore[arg-type]
        started = time.monotonic()
        report = distill.distill(store, baseline.SESSION, messages, ask)
        elapsed = time.monotonic() - started
        run = reasoner.runs[0]
        session = run.run._session
        results = run.run.results
        written = [name for batch in report.batches for name in batch.written]
        records = [store.find(name) for name in written]
        replies = [result.text for result in results]
        session_home = pathlib.Path(session._scratch.name) / "codex-home"
        return {
            "pair": pair,
            "mode": APP_SERVER_MODE,
            "wall_seconds": round(elapsed, 3),
            "batch_seconds": [round(elapsed, 3)],
            "startup_seconds": round(session.startup_seconds, 3),
            "reasoner_seconds_by_call": [round(result.seconds, 3) for result in results],
            "model_turn_seconds_by_call": session.model_turn_seconds,
            "agent_rounds": sum(batch.rounds for batch in report.batches),
            "cli_process_starts": session.process_starts,
            "reasoner_calls": len(results),
            "prompt_chars": sum(len(prompt) for prompt in run.prompts),
            "prompt_chars_by_call": [len(prompt) for prompt in run.prompts],
            "input_tokens_by_call": [result.input_tokens for result in results],
            "input_tokens_incremental_by_call": [result.input_tokens for result in results],
            "cached_input_tokens_by_call": [result.cached_input_tokens for result in results],
            "cached_input_tokens_incremental_by_call": [
                result.cached_input_tokens for result in results
            ],
            "output_tokens_by_call": [result.output_tokens for result in results],
            "input_tokens_cumulative": sum(result.input_tokens or 0 for result in results),
            "cached_input_tokens_cumulative": sum(
                result.cached_input_tokens or 0 for result in results
            ),
            "recall_calls": sum('"look":"recall"' in reply.replace(" ", "") for reply in replies),
            "read_calls": sum('"look":"read"' in reply.replace(" ", "") for reply in replies),
            "written": written,
            "rejected": [item for batch in report.batches for item in batch.rejected],
            "pending": sum(batch.pending for batch in report.batches),
            "provenance_valid": bool(records)
            and all(record is not None and record.provenance for record in records),
            "old_superseded": not store.find(baseline.OLD_NAME).is_active(),
            "session_ids": [result.session_id or None for result in results],
            "session_home_released": not session_home.exists(),
            "errors": [result.error for result in results if not result.ok],
            "event_methods": dict(sorted(session.event_methods.items())),
            "item_types": dict(sorted(session.item_types.items())),
            "native_tool_items": sum(
                count
                for item_type, count in session.item_types.items()
                if item_type not in APP_SERVER_ALLOWED_ITEMS
            ),
            "replies": replies,
        }


def summarize(results: list[dict[str, object]]) -> dict[str, object]:
    summary: dict[str, object] = {}
    for mode in ("stateless", "stateful", APP_SERVER_MODE):
        selected = [row for row in results if row["mode"] == mode]
        seconds = [float(row["wall_seconds"]) for row in selected]
        summary[mode] = {
            "runs": len(selected),
            "mean_seconds": round(statistics.mean(seconds), 3),
            "median_seconds": round(statistics.median(seconds), 3),
            "min_seconds": min(seconds),
            "max_seconds": max(seconds),
            "process_starts": [row["cli_process_starts"] for row in selected],
            "reasoner_calls": [row["reasoner_calls"] for row in selected],
            "prompt_chars": [row["prompt_chars"] for row in selected],
        }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=1, choices=range(1, 6))
    parser.add_argument("--only", choices=("stateless", "stateful", APP_SERVER_MODE))
    parser.add_argument("--out", type=pathlib.Path)
    args = parser.parse_args()
    results: list[dict[str, object]] = []
    rotations = (
        ("stateless", "stateful", APP_SERVER_MODE),
        ("stateful", APP_SERVER_MODE, "stateless"),
        (APP_SERVER_MODE, "stateless", "stateful"),
    )
    for pair in range(1, args.runs + 1):
        modes = (args.only,) if args.only else rotations[(pair - 1) % len(rotations)]
        for mode in modes:
            result = app_server_arm(pair) if mode == APP_SERVER_MODE else baseline._arm(mode, pair)
            results.append(result)
            print(json.dumps(result, sort_keys=True), flush=True)
    payload = {
        "model": baseline.MODEL,
        "scenario": "forced Recall -> Read -> SUPERSEDE",
        "runs": args.runs,
        "results": results,
        "summary": summarize(results) if not args.only else {},
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
