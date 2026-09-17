"""Fail a read-side pilot before scaling if its retrieval contrast never ran.

This is an execution gate, not a statistical test. Keep its report with the pilot.
"""

import argparse
import json
import re
import sqlite3
from pathlib import Path

ARMS = ("baseline", "raw", "gate")
PROBE_EPISODE = "gpt4_7abb270c"
PROBE_QUERY = "museum"
SHELL_COMMAND = re.compile(r"^/bin/bash -lc [\"']", re.MULTILINE)
# Pilot feasibility gates: at least half the 12 questions must retrieve something,
# and both competing Raw paths must be observed. Passing does not establish effect.


def index_counts(root):
    db = root / ".index" / "index.db"
    if not db.is_file():
        return 0, 0
    with sqlite3.connect(db) as connection:
        return (
            connection.execute("select count(*) from records").fetchone()[0],
            connection.execute("select count(*) from raw_chunks").fetchone()[0],
        )


def probe_hits(root):
    with sqlite3.connect(root / ".index" / "index.db") as connection:
        return (
            connection.execute(
                "select count(*) from chunks where chunks match ?", (PROBE_QUERY,)
            ).fetchone()[0],
            connection.execute(
                "select count(*) from raw_chunks where raw_chunks match ?", (PROBE_QUERY,)
            ).fetchone()[0],
        )


def limited(value):
    if isinstance(value, dict):
        return bool(value.get("truncated")) or any(limited(item) for item in value.values())
    if isinstance(value, list):
        return any(limited(item) for item in value)
    return False


def shell_commands(host_events):
    commands = []
    for event in host_events:
        transcript = event.get("stderr", "")
        if not isinstance(transcript, str):
            continue
        commands.extend(line for line in transcript.splitlines() if SHELL_COMMAND.match(line))
    return commands


def direct_store_commands(host_events):
    commands = []
    for line in shell_commands(host_events):
        if "/input-stores/" in line:
            command = line.partition("-lc ")[2]
            if not re.match(r"^[\"']mem(?:\s|[\"'])", command):
                commands.append(line[:300])
    return commands


def stores(panel):
    source = panel / "frozen-stores" / "W2"
    ids = json.loads((panel / "panel.json").read_text())["selected_ids"]
    failures = []
    for episode_id in ids:
        expected = index_counts(source / episode_id)
        if min(expected) <= 0:
            failures.append(f"source {episode_id}: no Memory or Raw index")
        for arm in ARMS:
            actual = index_counts(panel / arm / "input-stores" / "W2" / episode_id)
            if actual != expected:
                failures.append(f"{arm}/{episode_id}: index {actual}, source {expected}")
    if PROBE_EPISODE not in ids:
        failures.append(f"missing registered retrieval probe {PROBE_EPISODE}")
    else:
        for arm in ARMS:
            root = panel / arm / "input-stores" / "W2" / PROBE_EPISODE
            if not (root / ".index" / "index.db").is_file() or min(probe_hits(root)) <= 0:
                failures.append(f"{arm}: {PROBE_QUERY!r} probe did not hit both Memory and Raw")
    return {"phase": "stores", "episodes": len(ids), "ok": not failures, "failures": failures}


def observations(panel, *, min_nonempty, min_baseline_raw, min_trace):
    summary = {}
    failures = []
    expected = set(json.loads((panel / "panel.json").read_text())["selected_ids"])
    for arm in ARMS:
        records_file = panel / arm / "run" / "runs.jsonl"
        if not records_file.is_file():
            failures.append(f"{arm}: missing pilot records")
            continue
        records = [json.loads(line) for line in records_file.read_text().splitlines() if line]
        actual = [record["episode_id"] for record in records]
        if (
            len(records) != len(expected)
            or set(actual) != expected
            or len(actual) != len(set(actual))
        ):
            failures.append(f"{arm}: pilot episode identity or count differs from manifest")
        nonempty_questions = deep_raw_questions = trace_questions = direct_read_questions = 0
        for record in records:
            path = Path(record.get("observation_path", ""))
            events_file = path / "tools.jsonl"
            host_file = path / "host.jsonl"
            if (
                record.get("status") != "ok"
                or not events_file.is_file()
                or not host_file.is_file()
                or list(path.glob("*.limited"))
            ):
                failures.append(f"{arm}/{record['episode_id']}: incomplete exam or observation")
                continue
            events = [json.loads(line) for line in events_file.read_text().splitlines()]
            host_events = [json.loads(line) for line in host_file.read_text().splitlines()]
            if any(limited(event) for event in events + host_events):
                failures.append(f"{arm}/{record['episode_id']}: truncated observation")
                continue
            if any(event.get("kind") == "tool_start" for event in events) and not shell_commands(
                host_events
            ):
                failures.append(
                    f"{arm}/{record['episode_id']}: host command transcript unavailable"
                )
                continue
            bypass = direct_store_commands(host_events)
            if bypass:
                direct_read_questions += 1
                failures.append(
                    f"{arm}/{record['episode_id']}: direct store shell read bypassed mem retrieval"
                )
            if not any(event.get("kind") == "exam_end" and event.get("ok") for event in events):
                failures.append(f"{arm}/{record['episode_id']}: no successful exam end")
                continue
            recalls = [event for event in events if event.get("kind") == "recall_return"]
            nonempty_questions += any(event.get("hits") for event in recalls)
            deep_raw_questions += any(
                event.get("deep")
                and any(hit.get("source") == "raw" for hit in event.get("hits", []))
                for event in recalls
            )
            trace_questions += any(
                event.get("kind") == "tool_return"
                and event.get("command") == "trace"
                and event.get("result", {}).get("messages")
                for event in events
            )
        summary[arm] = {
            "questions": len(records),
            "nonempty_recall_questions": nonempty_questions,
            "deep_raw_questions": deep_raw_questions,
            "trace_with_messages_questions": trace_questions,
            "direct_store_read_questions": direct_read_questions,
        }
        if nonempty_questions < min_nonempty:
            failures.append(
                f"{arm}: retrieval engaged on only {nonempty_questions}/{len(records)} questions"
            )
    if summary.get("baseline", {}).get("deep_raw_questions", 0) < min_baseline_raw:
        failures.append("baseline: global deep Raw search never returned evidence")
    if summary.get("raw", {}).get("trace_with_messages_questions", 0) < min_trace:
        failures.append("raw: bound Trace did not return evidence on enough questions")
    return {"phase": "pilot", "arms": summary, "ok": not failures, "failures": failures}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("stores", "pilot"))
    parser.add_argument("--panel", required=True, type=Path)
    parser.add_argument("--min-nonempty", type=int, default=6)
    parser.add_argument("--min-baseline-raw", type=int, default=1)
    parser.add_argument("--min-trace", type=int, default=2)
    args = parser.parse_args()
    result = (
        stores(args.panel)
        if args.phase == "stores"
        else observations(
            args.panel,
            min_nonempty=args.min_nonempty,
            min_baseline_raw=args.min_baseline_raw,
            min_trace=args.min_trace,
        )
    )
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
