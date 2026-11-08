"""The per-run Write trace: ordered events, redaction, digests, and the size bound."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import pathlib

from agent_memory.core import write_trace
from agent_memory.core.redaction import REDACTED

SECRET = "sk-ABCDEFGHIJKLMNOPQRSTUVWX"


def _trace(store, name: str = "job", **overrides) -> write_trace.WriteTrace:
    config = dataclasses.replace(store.config.write.jobs, **overrides)
    path = store.layout.write_traces / f"{name}.jsonl"
    return write_trace.WriteTrace(path, config), path


def _events(path: pathlib.Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_events_are_appended_in_order_with_their_payloads(store):
    trace, path = _trace(store)
    trace.run_started("job-1", "boundary", 4, "host/claude-code")
    trace.batch("sessions/boundary#0-3", 120, 6)
    trace.round(1)
    trace.tool_call("recall", {"query": "queue timeout"})
    trace.operations(
        ["queue-timeout"],
        [{"operation": "new", "errors": [{"field": "abstract", "reason": "required"}]}],
    )
    trace.repair(1, 2)
    trace.usage({"input_tokens": 10, "output_tokens": 5})
    trace.error("ReasonerUnavailableError", "host unavailable")
    trace.run_finished(1, 1, 0, 1.5)

    events = _events(path)
    assert [event["event"] for event in events] == [
        "run_started",
        "batch",
        "round",
        "tool_call",
        "operations",
        "repair",
        "usage",
        "error",
        "run_finished",
    ]
    assert events[0]["job"] == "job-1"
    assert events[0]["session"] == "boundary"
    assert events[0]["target"] == 4
    assert events[0]["reasoner"] == "host/claude-code"
    assert events[1]["pointer"] == "sessions/boundary#0-3"
    assert events[1]["chars"] == 120
    assert events[1]["slots"] == 6
    assert events[2]["round"] == 1
    assert events[4]["applied"] == ["queue-timeout"]
    assert events[4]["rejected"][0]["errors"] == [{"field": "abstract", "reason": "required"}]
    assert events[5]["leftovers"] == 2
    assert events[6]["usage"] == {"input_tokens": 10, "output_tokens": 5}
    assert events[7]["kind"] == "ReasonerUnavailableError"
    assert events[8]["written"] == 1
    assert events[8]["rejected"] == 1
    assert events[8]["pending"] == 0
    assert all("at" in event for event in events)


def test_every_string_is_redacted_before_it_reaches_the_file(store):
    trace, path = _trace(store)
    trace.run_started("job-1", f"session-with-{SECRET}", 1, "host")
    trace.tool_call("recall", {"query": f"leak {SECRET}"})
    trace.operations(
        [],
        [
            {
                "operation": "new",
                "errors": [{"field": "body", "reason": f"password: hunter2 {SECRET}"}],
            }
        ],
    )
    trace.error("RuntimeError", f"endpoint refused for {SECRET}")

    rendered = path.read_text(encoding="utf-8")
    assert SECRET not in rendered
    assert rendered.count(REDACTED) >= 4


def test_arguments_stay_digests_until_bodies_are_enabled(store):
    arguments = {"query": "queue timeout"}
    off, off_path = _trace(store, name="digests-only")
    off.tool_call("recall", arguments)
    on, on_path = _trace(store, name="with-bodies", trace_bodies=True)
    on.tool_call("recall", arguments)

    off_event = _events(off_path)[0]
    rendered = json.dumps(arguments, sort_keys=True, ensure_ascii=False)
    assert off_event["digest"] == hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    assert off_event["length"] == len(rendered)
    assert "arguments" not in off_event
    assert _events(on_path)[0]["arguments"] == arguments


def test_the_size_cap_appends_one_truncation_and_then_stops(store):
    trace, path = _trace(store, trace_max_bytes=400)
    for _ in range(6):
        trace.tool_call("recall", {"query": "x" * 120})

    events = _events(path)
    assert events[-1]["event"] == "truncated"
    assert [event["event"] for event in events].count("truncated") == 1
    before = len(events)

    trace.tool_call("recall", {"query": "after the cap"})
    trace.round(9)

    assert len(_events(path)) == before


def test_a_zero_bound_truncates_at_the_first_event(store):
    trace, path = _trace(store, trace_max_bytes=0)
    trace.run_started("job-1", "boundary", 1, "host")

    assert [event["event"] for event in _events(path)] == ["truncated"]


def test_read_skips_torn_lines_and_redacts_what_it_returns(store):
    trace, path = _trace(store)
    trace.run_started("job-1", f"session-with-{SECRET}", 1, "host")
    trace.run_finished(1, 0, 0, 0.1)
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"event": "torn", "messa')

    events = write_trace.read(path, store.config.write.jobs)

    assert [event["event"] for event in events] == ["run_started", "run_finished"]
    assert SECRET not in json.dumps(events)


def test_read_stops_at_its_bound(store):
    path = store.layout.write_traces / "bounded.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps({"event": f"event-{number}", "pad": "x" * 40}) + "\n" for number in range(4)
    ]
    path.write_text("".join(lines), encoding="utf-8")
    config = dataclasses.replace(store.config.write.jobs, trace_max_bytes=2 * len(lines[0]))

    events = write_trace.read(path, config)

    assert [event["event"] for event in events] == ["event-0", "event-1"]


def test_read_of_a_missing_or_empty_trace_is_empty(store):
    trace, path = _trace(store, name="absent")

    assert write_trace.read(path, store.config.write.jobs) == []
    assert write_trace.read(store.layout.write_traces / "nope.jsonl", store.config.write.jobs) == []
