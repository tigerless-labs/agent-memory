"""Authenticated Claude Code coverage for the complete native Write path."""

from __future__ import annotations

import dataclasses
import pathlib

import pytest
from agent_memory.core import distill, reconcile, sessions, toolkit
from agent_memory.core.config import Config, ExecutorConfig
from agent_memory.core.errors import ReasonerUnavailableError, ValidationError
from agent_memory.core.store import Store
from agent_memory.core.watermark import Watermark
from agent_memory.executor import distiller as executor_distiller
from agent_memory.executor.hosts import HOST_CLAUDE_CODE
from agent_memory.executor.reasoners import ToolHostReasoner
from claude_live import Recording, case, describe, model, requires_live_claude

pytestmark = requires_live_claude

WRITE_TOOLS = {toolkit.TOOL_RECALL, toolkit.TOOL_READ, toolkit.TOOL_SUBMIT}


def _store(tmp_path: pathlib.Path) -> Store:
    store = Store(tmp_path / "store", config=Config.default(), agent="claude-live")
    store.init()
    return store


def _reasoner(instruction_suffix: str = "") -> Recording:
    chosen = executor_distiller.distiller(ExecutorConfig(host=HOST_CLAUDE_CODE, host_model=model()))
    assert isinstance(chosen, ToolHostReasoner)
    return Recording(chosen, instruction_suffix)


def _messages(store: Store, session: str, lines: list[str]):
    pointer = store.archive.append_session(session, lines)
    return sessions.resolve(store.layout, pointer)


def _files(store: Store) -> dict[str, str]:
    root = pathlib.Path(store.root)
    return {
        str(path.relative_to(root)): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*.md"))
        if ".index" not in path.parts
    }


def _assert_only_write_tools_were_called(recording: Recording) -> None:
    called = recording.tool_names()
    assert called, "the Host listed tools but called none"
    assert set(called) <= WRITE_TOOLS


def test_live_claude_new_memory_is_committed_with_provenance_and_watermark(tmp_path):
    with case("write-new", "a durable fact becomes one new Memory") as entry:
        store = _store(tmp_path)
        lines = [
            "user: For project aurora, the deployment window is Friday at 22:00 UTC. "
            "This is a stable fact worth remembering.",
            "assistant: Understood.",
        ]
        reasoner = _reasoner()
        report = distill.distill(store, "live-new", _messages(store, "live-new", lines), reasoner)
        entry.update(describe(reasoner))
        _assert_only_write_tools_were_called(reasoner)
        assert reasoner.tool_names()[-1] == toolkit.TOOL_SUBMIT
        assert any(op.get("op") == "new" for op in reasoner.record["submission"])
        written = report.batches[0].written
        assert written
        record = store.find(written[0])
        entry["committed"] = record.to_text()
        assert record.is_active()
        assert record.abstract.strip()
        assert "friday" in (record.abstract + record.body).lower()
        assert record.provenance
        assert all(pointer.startswith("sessions/live-new#") for pointer in record.provenance)
        assert Watermark(store.layout, store.clock).read("live-new").distilled == len(lines)


def test_live_claude_recalls_reads_and_supersedes(tmp_path):
    with case("write-supersede", "recall and read the old Memory, then supersede it") as entry:
        store = _store(tmp_path)
        old = store.record(
            name="queue-timeout",
            type="fact",
            fields={"project": "aurora", "subject": "queue timeout"},
            abstract="Project aurora queue timeout is 20 seconds",
            body="The queue timeout is configured to 20 seconds.",
        )
        reasoner = _reasoner(
            "\n\nLive validation requirement: call recall for the old queue timeout, then call "
            "read on the matching handle before submit_operations."
        )
        lines = [
            "user: Project aurora's queue timeout is now 30 seconds, replacing the old "
            "20 second value. This is a durable configuration change.",
            "assistant: Understood.",
        ]
        report = distill.distill(
            store, "live-supersede", _messages(store, "live-supersede", lines), reasoner
        )
        entry.update(describe(reasoner))
        _assert_only_write_tools_were_called(reasoner)
        names = reasoner.tool_names()
        assert names[-1] == toolkit.TOOL_SUBMIT
        assert names.index(toolkit.TOOL_RECALL) < names.index(toolkit.TOOL_READ)
        assert any(op.get("op") == "supersede" for op in reasoner.record["submission"])
        retired = store.find(old.name)
        assert not retired.is_active()
        written = report.batches[0].written
        assert written
        successor = store.find(written[0])
        entry["committed"] = {"old": retired.to_text(), "new": successor.to_text()}
        assert successor.is_active()
        assert retired.superseded_by == successor.name
        assert "30" in successor.abstract + successor.body
        assert Watermark(store.layout, store.clock).read("live-supersede").distilled == len(lines)


def test_live_claude_skips_a_session_without_durable_information(tmp_path):
    with case("write-skip", "small talk yields a submitted Skip and no Memory") as entry:
        store = _store(tmp_path)
        store.config.write.event_lane = False
        before = _files(store)
        lines = ["user: Thanks.", "assistant: You're welcome."]
        reasoner = _reasoner()
        try:
            report = distill.distill(
                store, "live-skip", _messages(store, "live-skip", lines), reasoner
            )
        finally:
            entry.update(describe(reasoner))
        _assert_only_write_tools_were_called(reasoner)
        operations = reasoner.record["submission"]
        assert operations and {operation["op"] for operation in operations} == {"skip"}
        assert report.batches[0].written == ()
        assert _files(store) == before
        assert Watermark(store.layout, store.clock).read("live-skip").distilled == len(lines)


def test_live_claude_recovers_from_a_tool_error_in_the_same_run(tmp_path):
    with case("write-tool-error", "an invalid read errors, then a valid Skip lands") as entry:
        store = _store(tmp_path)
        messages = _messages(store, "live-tool-error", ["user: No durable information."])
        write_toolkit = toolkit.WriteToolkit(
            store, reconcile.build(store, "live-tool-error", messages)
        )
        reasoner = _reasoner()
        reasoner.converse(
            "This is a transport test. First call read with name missing-memory. After its "
            "error, call submit_operations with exactly one operation: op skip and type fact.",
            "Exercise the Memory tool error round trip now.",
            write_toolkit,
        )
        entry.update(describe(reasoner))
        assert [call.name for call in write_toolkit.calls] == [
            toolkit.TOOL_READ,
            toolkit.TOOL_SUBMIT,
        ]
        assert write_toolkit.calls[0].reply.is_error
        assert not write_toolkit.calls[1].reply.is_error
        assert [operation["op"] for operation in write_toolkit.submission] == ["skip"]


def test_live_claude_refused_submission_leaves_store_and_watermark_unchanged(tmp_path):
    with case("write-refused", "a refused run writes nothing, holds the watermark") as entry:
        store = _store(tmp_path)
        store.config.write.event_lane = False
        before = _files(store)
        reasoner = _reasoner(
            "\n\nThis run is a fail-safety transport test. Call submit_operations exactly once "
            'with this single operation: {"op": "supersede", "type": "fact", '
            '"handle": "no-such-memory"}. The store will refuse it. After the refusal, end the '
            "run with a one-line text reply and call no further tools."
        )
        lines = ["user: Project aurora's build cache lives in /var/cache/aurora."]
        with pytest.raises(ValidationError, match="submitted no operations"):
            try:
                distill.distill(
                    store, "live-refused", _messages(store, "live-refused", lines), reasoner
                )
            finally:
                entry.update(describe(reasoner))
        submissions = [
            call for call in reasoner.record["calls"] if call["name"] == toolkit.TOOL_SUBMIT
        ]
        assert submissions and all(call["is_error"] for call in submissions)
        assert reasoner.record["submission"] is None
        assert _files(store) == before
        assert Watermark(store.layout, store.clock).read("live-refused").distilled == 0


def test_live_claude_host_timeout_fails_closed(tmp_path):
    with case("write-timeout", "a Host killed mid-run writes nothing") as entry:
        store = _store(tmp_path)
        store.config.write.event_lane = False
        before = _files(store)
        reasoner = _reasoner()
        host = reasoner.host.host
        host.spec = dataclasses.replace(host.spec, timeout_seconds=1.0, attempts=1)
        lines = ["user: Project aurora's release train leaves every Tuesday."]
        with pytest.raises(ReasonerUnavailableError, match="timeout"):
            try:
                distill.distill(
                    store, "live-timeout", _messages(store, "live-timeout", lines), reasoner
                )
            finally:
                entry.update(describe(reasoner))
        assert _files(store) == before
        assert Watermark(store.layout, store.clock).read("live-timeout").distilled == 0
