"""Reproduce one-revision paired adaptive-read evaluation on the fixed Codex 12."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import sqlite3
import statistics
import subprocess
import sys

from agent_memory.core.recall import Recall
from agent_memory.core.store import Store

ARMS = ("baseline", "treatment")
PILOT = ("7e974930", "gpt4_7abb270c")
SOURCE_RELATIVE = "experiments/runs/codex-read12-20260914"
SUITE_RELATIVE = "experiments/runs/raw-evidence-read-20260918/suite.json"
DEFAULT_OUTPUT = "experiments/runs/adaptive-read-12-20260918"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def truth(root: pathlib.Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): digest(path.read_bytes())
        for path in sorted(root.rglob("*"))
        if path.is_file() and not set(path.relative_to(root).parts) & {".index", ".state"}
    }


def write_json(path: pathlib.Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def revision(code: pathlib.Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=code, text=True).strip()


def source_manifest(source: pathlib.Path) -> list[dict]:
    suite = json.loads((source / SUITE_RELATIVE).read_text(encoding="utf-8"))
    panel = json.loads((source / SOURCE_RELATIVE / "panel.json").read_text(encoding="utf-8"))
    assert len(suite) == 12 and {q["question_id"] for q in suite} == set(panel["selected_ids"])
    for question in suite:
        assert question["question"] and question["answer"]
        assert question["answer_session_ids"]
        assert set(question["answer_session_ids"]) <= set(question["haystack_session_ids"])
    return suite


def prepare(code: pathlib.Path, source: pathlib.Path, output: pathlib.Path) -> None:
    suite = source_manifest(source)
    write_json(output / "question_manifest.json", [
        {
            "id": q["question_id"], "question": q["question"],
            "answer": q["answer"], "answer_session_ids": q["answer_session_ids"],
            "source_session_ids": q["haystack_session_ids"],
        } for q in suite
    ])
    write_json(output / "suite.json", suite)
    write_json(output / "pilot-suite.json", [q for q in suite if q["question_id"] in PILOT])
    audit = {
        "revision": revision(code), "source_panel": SOURCE_RELATIVE,
        "panel_sha256": digest((source / SOURCE_RELATIVE / "panel.json").read_bytes()),
        "suite_sha256": digest((source / SUITE_RELATIVE).read_bytes()),
        "stores": {},
    }
    for question in suite:
        identifier = question["question_id"]
        canonical = source / SOURCE_RELATIVE / "frozen-stores" / "W2" / identifier
        original = truth(canonical)
        assert canonical.is_dir() and len(original) > 1, identifier
        result = {"truth_sha256": digest(json.dumps(original, sort_keys=True).encode()),
                  "memory_files": 0, "arms": {}}
        for arm in ARMS:
            target = output / arm / "input-stores" / "W2" / identifier
            if target.exists():
                raise FileExistsError(f"refusing to overwrite existing experiment store: {target}")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(canonical, target, ignore=shutil.ignore_patterns(".index", ".state"))
            assert truth(target) == original
            store = Store(target)
            store.sync_index()
            records = store.records()
            assert records, identifier
            result["memory_files"] = len(records)
            with sqlite3.connect(target / ".index/index.db") as connection:
                indexed = connection.execute("select count(*) from records").fetchone()[0]
            assert indexed >= len(records) > 0
            words = question["question"].replace("?", "").split()
            probe = " ".join(words[:8])
            hits = Recall(store).recall(probe, log=False)
            if not hits:
                probe = records[0].abstract
                hits = Recall(store).recall(probe, log=False)
            assert hits and store.read(hits[0].name, level="full").text.strip(), identifier
            assert truth(target) == original
            result["arms"][arm] = {
                "indexed_docs": indexed, "probe_query": probe,
                "probe_hit_count": len(hits), "read_name": hits[0].name,
            }
        audit["stores"][identifier] = result
    write_json(output / "preflight.json", audit)
    print(f"preflight: {len(audit['stores'])}/12 indexed, read-enabled paired stores")


def environment(code: pathlib.Path, source: pathlib.Path) -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(str(code / "packages" / pkg / "src") for pkg in (
        "core", "cli", "harness", "executor", "adapters", "mcp"
    ))
    env["PATH"] = os.pathsep.join((
        str(source / SOURCE_RELATIVE / "bin"), str(source / ".venv/bin"), env["PATH"]
    ))
    return env


def run(code: pathlib.Path, source: pathlib.Path, output: pathlib.Path, phase: str, arm: str) -> None:
    assert (output / "preflight.json").is_file()
    assert arm in ARMS and phase in ("pilot", "full")
    assert revision(code) == json.loads((output / "preflight.json").read_text())["revision"]
    folder = output / phase / arm
    folder.mkdir(parents=True, exist_ok=True)
    suite = output / ("pilot-suite.json" if phase == "pilot" else "suite.json")
    workspace = folder / "run"
    command = [
        str(source / ".venv/bin/mem-exp"), "run", "--suite", str(suite),
        "--workspace", str(workspace), "--arms", "W2", "--per-type", "2",
        "--seed", "20260901", "--reuse-stores", str(output / arm / "input-stores"),
        "--run-id", f"adaptive-read-{phase}-{arm}", "--host", "codex",
        "--model", "gpt-5.6-sol", "--judge-host", "codex", "--judge-model", "gpt-5.6-sol",
        "--exam-mode", "agentic", "--exam-max-turns", "20", "--concurrency", "1",
        "--observe-reads", "--set", f"recall.adaptive_read_enabled={str(arm == 'treatment').lower()}",
    ]
    write_json(folder / "command.json", {"command": command, "revision": revision(code),
                                          "cwd": str(code), "PYTHONPATH": environment(code, source)["PYTHONPATH"]})
    with (folder / "execution.log").open("w", encoding="utf-8") as log:
        completed = subprocess.run(command, cwd=code, env=environment(code, source),
                                   stdout=log, stderr=subprocess.STDOUT, check=False)
    print(f"{phase}/{arm}: exit {completed.returncode} (see {folder / 'execution.log'})")
    if completed.returncode:
        raise SystemExit(completed.returncode)


def traces(output: pathlib.Path, phase: str, arm: str) -> dict[str, dict]:
    workspace = output / phase / arm / "run"
    rows = [json.loads(line) for line in (workspace / "runs.jsonl").read_text().splitlines()]
    parsed = {}
    for row in rows:
        events = []
        path = pathlib.Path(row["observation_path"])
        for channel in ("tools", "host"):
            event_file = path / f"{channel}.jsonl"
            if event_file.exists():
                events.extend(json.loads(line) for line in event_file.read_text().splitlines())
        events.sort(key=lambda event: event.get("at_ns", 0))
        recalls = [event for event in events if event["kind"] == "tool_start"
                   and event.get("arguments", {}).get("command") in ("recall", "context")]
        returned = [event for event in events if event["kind"] == "recall_return"]
        reads = [event for event in events if event["kind"] == "read_return"
                 and event.get("level") == "full"]
        followups = [event for event in recalls
                     if event["arguments"].get("round") == "follow-up"]
        followup_start = min((event["at_ns"] for event in followups), default=None)
        parsed[row["episode_id"]] = {
            "correct": row["correct"], "status": row["status"], "answer": row["answer"],
            "expected": row["expected"], "exam_seconds": row["exam_seconds"],
            "recalls": [event["arguments"] for event in recalls],
            "recall_hits": [len(event["hits"]) for event in returned],
            "reads": [event["name"] for event in reads],
            "follow_up_reads": [event["name"] for event in reads
                                if followup_start and event["at_ns"] > followup_start],
            "empty_recall_count": sum(not event["hits"] for event in returned),
            "follow_up_queries": [event["arguments"].get("query") for event in followups],
            "errors": [event for event in events if event["kind"] in
                       ("tool_error", "host_error", "evidence_limit")],
            "observation_path": row["observation_path"],
        }
    return parsed


def report(output: pathlib.Path, phase: str) -> None:
    baseline, treatment = (traces(output, phase, arm) for arm in ARMS)
    assert baseline.keys() == treatment.keys()
    paired = {identifier: {"baseline": baseline[identifier], "treatment": treatment[identifier]}
              for identifier in sorted(baseline)}
    write_json(output / ("paired_results.json" if phase == "full" else "pilot_results.json"), paired)
    for arm, records in (("baseline", baseline), ("treatment", treatment)):
        values = list(records.values())
        latencies = sorted(item["exam_seconds"] for item in values)
        print(arm, "correct", sum(item["correct"] for item in values), "/", len(values),
              "recall", sum(bool(item["recalls"]) for item in values),
              "read", sum(bool(item["reads"]) for item in values),
              "follow-up", sum(bool(item["follow_up_queries"]) for item in values),
              "median latency", statistics.median(latencies))
    print("flips", [(identifier, a["correct"], treatment[identifier]["correct"])
                    for identifier, a in baseline.items()
                    if a["correct"] != treatment[identifier]["correct"]])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "run", "report"))
    parser.add_argument("--code", type=pathlib.Path, required=True)
    parser.add_argument("--source", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--phase", choices=("pilot", "full"), default="pilot")
    parser.add_argument("--arm", choices=ARMS, default="treatment")
    args = parser.parse_args()
    code, source, output = (path.resolve() for path in (args.code, args.source, args.output))
    if args.action == "prepare":
        prepare(code, source, output)
    elif args.action == "run":
        run(code, source, output, args.phase, args.arm)
    else:
        report(output, args.phase)


if __name__ == "__main__":
    main()
