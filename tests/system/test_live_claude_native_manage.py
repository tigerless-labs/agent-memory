"""Authenticated Claude Code coverage for the complete native Manage review path."""

from __future__ import annotations

import pathlib

import pytest
from agent_memory.core.config import OperationExecutorConfig
from agent_memory.core.errors import ValidationError
from agent_memory.core.ledger import LEDGER_FILENAME
from agent_memory.core.manage import Manage
from agent_memory.core.manage_toolkit import TOOL_LIST, TOOL_READ, TOOL_SUBMIT
from agent_memory.core.store import Store
from agent_memory.executor import distiller as executor_distiller
from agent_memory.executor import selection
from agent_memory.executor.reasoners import ToolHostReasoner
from claude_live import Recording, case, describe, model, requires_live_claude

pytestmark = requires_live_claude

REVIEW_TOOLS = {TOOL_LIST, TOOL_READ, TOOL_SUBMIT}
DECIDED = {"accepted": True, "rejected": False}


def _store(tmp_path: pathlib.Path) -> Store:
    store = Store(tmp_path / "store", agent="claude-live-manage-seed")
    store.init()
    store.config.manage.git_commit = False
    store.config.executor.manage = OperationExecutorConfig(
        reasoner="host",
        host="claude-code",
        host_model=model(),
        tool_mode="native",
        timeout_seconds=240.0,
    )
    store.config.save(store.root)
    return store


def _reasoner(store: Store, instruction_suffix: str = "") -> Recording:
    configured = selection.resolve(store.config.executor, selection.MANAGE)
    chosen = executor_distiller.distiller(configured)
    assert isinstance(chosen, ToolHostReasoner)
    return Recording(chosen, instruction_suffix)


def _snapshot(store: Store) -> dict[str, str]:
    return {record.name: record.to_text() for record in store.records(include_invalid=True)}


def _queue_window(store: Store) -> None:
    store.record(
        type="fact",
        name="queue-window-old",
        abstract="Queue drain window closes before worker lease",
        body="The original note says the drain window is shorter than the lease.",
    )
    store.record(
        type="fact",
        name="queue-window-current",
        abstract="Queue drain window closes before worker lease on staging",
        body=(
            "On staging the queue drain window is 20 seconds and the worker lease is 30 seconds. "
            "Raise drain_timeout above the lease TTL."
        ),
    )


def _distinct_services(store: Store) -> None:
    store.record(
        type="fact",
        name="orion-drain-window",
        abstract="Queue drain window closes before the worker lease on the orion service",
        body="The orion service drains its queue for 20 seconds before shutdown.",
    )
    store.record(
        type="fact",
        name="vega-drain-window",
        abstract="Queue drain window closes before the worker lease on the vega service",
        body=(
            "The vega service drains its queue for 45 seconds before shutdown. Vega and orion "
            "are separate services with separate configuration."
        ),
    )


def _review(store: Store, reasoner: Recording, entry: dict[str, object]):
    proposals = Manage(store).proposals()
    assert proposals, "the fixture must yield a T1 proposal"
    targets = {proposal.id: set(proposal.targets) for proposal in proposals}
    entry["proposals"] = [proposal.as_dict() for proposal in proposals]
    try:
        report = Manage(store).sleep(reasoner=reasoner)
    finally:
        entry.update(describe(reasoner))
    review = report.review
    names = [name for name, _ in review.tool_trace]
    entry["review"] = {
        "complete": review.complete,
        "tool_trace": review.tool_trace,
        "evidence_reads": review.evidence_reads,
        "agent_turns": review.agent_turns,
        "input_tokens": review.input_tokens,
        "cached_input_tokens": review.cached_input_tokens,
        "output_tokens": review.output_tokens,
        "duration_seconds": review.duration_seconds,
        "apply_seconds": review.apply_seconds,
    }
    entry["decisions"] = [decision.as_dict() for decision in report.decisions]
    entry["withheld"] = list(report.withheld)

    assert review.mode == "native"
    assert review.complete
    assert set(names) <= REVIEW_TOOLS
    assert TOOL_LIST not in names or names[0] == TOOL_LIST
    assert TOOL_READ in names
    assert names[-1] == TOOL_SUBMIT
    assert review.agent_turns and review.output_tokens
    for proposal_id, name in review.evidence_reads:
        assert name in targets[proposal_id]
    decided = {decision.proposal_id for decision in report.decisions}
    assert decided | set(report.withheld) == set(targets)
    assert pathlib.Path(report.path).is_file()
    assert (store.layout.dream_reports / LEDGER_FILENAME).is_file()
    return report, targets


def _assert_state_follows_verdicts(store: Store, report, targets) -> None:
    reopened = Store(store.root, agent="assert")
    for decision in report.decisions:
        payload = decision.as_dict()
        active = [reopened.find(name).is_active() for name in sorted(targets[decision.proposal_id])]
        if DECIDED[payload["verdict"]]:
            assert False in active
        else:
            assert all(active)


def test_live_claude_reviews_a_supersede_and_the_store_follows_its_verdict(tmp_path):
    with case("manage-review", "list, read evidence, submit; Manage applies") as entry:
        store = _store(tmp_path)
        _queue_window(store)
        report, targets = _review(store, _reasoner(store), entry)
        _assert_state_follows_verdicts(store, report, targets)
        entry["final_store"] = _snapshot(Store(store.root, agent="assert"))


def test_live_claude_reviews_a_questionable_merge_without_being_forced(tmp_path):
    with case("manage-distinct", "a merge across separate services is judged freely") as entry:
        store = _store(tmp_path)
        _distinct_services(store)
        report, targets = _review(store, _reasoner(store), entry)
        _assert_state_follows_verdicts(store, report, targets)
        entry["final_store"] = _snapshot(Store(store.root, agent="assert"))


def test_live_claude_sees_refused_ids_and_still_completes(tmp_path):
    with case("manage-refusals", "foreign ids are refused and the run then completes") as entry:
        store = _store(tmp_path)
        _queue_window(store)
        reasoner = _reasoner(
            store,
            "\n\nLive validation requirement: after list_proposals, first call read_evidence "
            "with proposal not-in-this-run and name queue-window-old, then call "
            "submit_verdicts with one verdict for proposal not-in-this-run. Both are refused; "
            "then review the listed proposal normally and submit its verdict.",
        )
        report, targets = _review(store, reasoner, entry)
        calls = reasoner.record["calls"]
        foreign = [call for call in calls if "not-in-this-run" in str(call["arguments"])]
        assert {call["name"] for call in foreign} == {TOOL_READ, TOOL_SUBMIT}
        assert all(call["is_error"] for call in foreign)
        _assert_state_follows_verdicts(store, report, targets)


def test_live_claude_without_a_submission_leaves_store_ledger_and_report_untouched(tmp_path):
    with case("manage-no-submission", "a run without verdicts fails closed") as entry:
        store = _store(tmp_path)
        _queue_window(store)
        before = _snapshot(store)
        reasoner = _reasoner(
            store,
            "\n\nThis run is a fail-safety transport test. Call list_proposals once, then end "
            "the run with a one-line text reply. Call no other tool in this run.",
        )
        with pytest.raises(ValidationError, match="submitted no complete verdict set"):
            try:
                Manage(store).sleep(reasoner=reasoner)
            finally:
                entry.update(describe(reasoner))
        assert TOOL_SUBMIT not in reasoner.tool_names()
        assert _snapshot(Store(store.root, agent="assert")) == before
        assert not list(store.layout.dream_reports.glob("*.md"))
        assert not (store.layout.dream_reports / LEDGER_FILENAME).exists()
