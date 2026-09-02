"""M6 — unattended Manage adds and amends; anything that loses a distinction is a proposal."""

import datetime as dt
import shutil

import pytest
from agent_memory.core.errors import AuthorityError, NotFoundError
from agent_memory.core.manage import (
    ACTION_DUPLICATE_MERGED,
    ACTION_LINK_ADDED,
    ACTION_STALENESS_MARKED,
    ACTION_WEIGHT_SETTLED,
    PROPOSAL_CLUSTER,
    PROPOSAL_MERGE,
    PROPOSAL_SUPERSEDE,
    Manage,
)
from agent_memory.core.recall import Recall
from agent_memory.core.record import STATUS_STALE


def _kinds(report):
    return {action.kind for action in report.actions}


def _proposal_kinds(report):
    return {proposal.kind for proposal in report.proposals}


def test_unattended_sleep_never_shrinks_the_store(seeded):
    before = len(seeded.records(include_archived=True))
    Manage(seeded).sleep()
    Manage(seeded).sleep()
    assert len(seeded.records(include_archived=True)) >= before


def test_sleep_is_idempotent(seeded):
    first = Manage(seeded).sleep()
    after_first = {record.name: record.to_text() for record in seeded.records()}
    second = Manage(seeded).sleep()
    after_second = {record.name: record.to_text() for record in seeded.records()}
    assert after_second == after_first
    assert _proposal_kinds(second) == _proposal_kinds(first)


def test_reading_a_memory_raises_its_weight_at_the_next_sleep(seeded):
    before = seeded.find("staging-deploy-e4021").weight
    seeded.read("staging-deploy-e4021")
    report = Manage(seeded).sleep()
    assert ACTION_WEIGHT_SETTLED in _kinds(report)
    assert seeded.find("staging-deploy-e4021").weight > before


def test_an_untouched_memory_decays_but_never_below_the_floor(seeded, clock):
    clock.advance(days=seeded.config.weight.decay_after_days * 2)
    for _ in range(int(seeded.config.weight.ceiling / seeded.config.weight.decay_step) + 1):
        Manage(seeded).sleep()
    assert all(record.weight >= seeded.config.weight.floor for record in seeded.records())


def test_decay_is_reversible_by_an_explicit_boost(seeded, clock):
    clock.advance(days=seeded.config.weight.decay_after_days * 2)
    Manage(seeded).sleep()
    decayed = seeded.find("file-truth-invariant").weight
    restored = seeded.feedback("file-truth-invariant", seeded.config.weight.boost_step)
    assert restored.weight > decayed


def test_long_idle_memories_are_marked_stale_rather_than_removed(seeded, clock):
    clock.advance(days=seeded.config.manage.stale_after_days + 1)
    report = Manage(seeded).sleep()
    assert ACTION_STALENESS_MARKED in _kinds(report)
    assert all(record.path.exists() for record in seeded.records())
    assert any(record.status == STATUS_STALE for record in seeded.records())


def test_exact_duplicates_are_merged_by_supersede_not_by_deletion(seeded):
    original = seeded.find("file-truth-invariant")
    seeded.record(
        abstract=original.abstract,
        type=original.type,
        domain=original.domain,
        body=original.body,
        name="file-truth-invariant-copy",
    )
    report = Manage(seeded).sleep()
    assert ACTION_DUPLICATE_MERGED in _kinds(report)
    copy = seeded.find("file-truth-invariant-copy")
    assert copy is not None
    assert copy.superseded_by == "file-truth-invariant"


def test_records_that_keep_surfacing_together_grow_links_between_them(seeded):
    for index in range(seeded.config.manage.link_cooccurrence_min):
        Recall(seeded).recall(f"deploy drain queue file truth concise answers {index}")
    report = Manage(seeded).sleep()
    assert ACTION_LINK_ADDED in _kinds(report)
    assert any(record.links for record in seeded.records())


def test_similar_but_not_identical_entries_become_a_proposal_not_an_edit(seeded):
    seeded.record(
        abstract="Ryan prefers concise answers with no preamble at all",
        type="preference",
        domain="user",
        name="ryan-concise-restated",
    )
    report = Manage(seeded).sleep()
    assert {PROPOSAL_MERGE, PROPOSAL_SUPERSEDE} & _proposal_kinds(report)
    assert seeded.find("ryan-concise-restated") is not None
    assert seeded.find("ryan-prefers-concise-answers") is not None


def test_a_crowded_domain_root_yields_a_clustering_proposal_that_is_not_executed(store):
    for index in range(store.config.manage.cluster_min_files):
        store.record(
            abstract=f"Deploy pipeline note number {index} about the release rollout",
            type="procedure",
            domain="project",
            name=f"deploy-note-{index}",
        )
    report = Manage(store).sleep()
    clusters = [item for item in report.proposals if item.kind == PROPOSAL_CLUSTER]
    assert clusters
    assert all(
        record.path.parent == store.layout.domain_dir("project") for record in store.records()
    )


def test_every_sleep_leaves_an_auditable_report(seeded):
    report = Manage(seeded).sleep()
    text = (seeded.layout.dream_reports / report.path.split("/")[-1]).read_text(encoding="utf-8")
    assert "proposals" in text
    assert report.inspected == len(seeded.records())


def test_trigger_needs_both_elapsed_time_and_new_sessions(seeded, clock):
    manage = Manage(seeded)
    assert not manage.due(sessions_since=0)
    assert manage.due(sessions_since=seeded.config.manage.trigger_min_sessions)

    manage.sleep()
    assert not Manage(seeded).due(sessions_since=seeded.config.manage.trigger_min_sessions)
    clock.advance(hours=seeded.config.manage.trigger_min_hours + 1)
    assert Manage(seeded, clock).due(sessions_since=seeded.config.manage.trigger_min_sessions)


def test_dates_are_normalised_to_calendar_days(seeded):
    target = seeded.find("file-truth-invariant")
    target.updated = dt.datetime(2026, 1, 15, 9, 30, tzinfo=dt.UTC).isoformat()
    target.path.write_text(target.to_text(), encoding="utf-8")
    seeded.sync_index()
    Manage(seeded).sleep()
    assert seeded.find("file-truth-invariant").updated == "2026-01-15"


def _twins(store):
    store.record(
        abstract="The nightly export job times out against the reporting replica",
        type="experience",
        domain="experience",
        body="Short note.",
        name="nightly-export-timeout",
    )
    store.record(
        abstract="The nightly export job times out against the reporting replica again",
        type="experience",
        domain="experience",
        body="Longer note with the drain window, the lease TTL, and the fix that worked.",
        name="nightly-export-timeout-followup",
    )
    return "nightly-export-timeout", "nightly-export-timeout-followup"


def _find(proposals, kind):
    return next(proposal for proposal in proposals if proposal.kind == kind)


def test_a_proposal_keeps_the_same_identity_across_sleeps(seeded):
    _twins(seeded)
    first = _find(Manage(seeded).sleep().proposals, PROPOSAL_SUPERSEDE)
    second = _find(Manage(seeded).sleep().proposals, PROPOSAL_SUPERSEDE)
    assert first.id == second.id


def test_a_decided_proposal_is_never_proposed_again(seeded):
    _twins(seeded)
    proposal = _find(Manage(seeded).proposals(), PROPOSAL_SUPERSEDE)
    Manage(seeded).decide(proposal.id, accept=False)
    assert proposal.id not in {open_one.id for open_one in Manage(seeded).proposals()}
    assert proposal.id not in {open_one.id for open_one in Manage(seeded).sleep().proposals}


def test_accepting_a_supersede_keeps_the_richer_entry(seeded):
    thin, rich = _twins(seeded)
    proposal = _find(Manage(seeded).proposals(), PROPOSAL_SUPERSEDE)
    Manage(seeded).decide(proposal.id, accept=True)
    assert seeded.find(rich).is_active()
    assert seeded.find(thin).superseded_by == rich


def test_accepting_a_supersede_loses_no_file(seeded):
    _twins(seeded)
    before = len(seeded.records(include_archived=True))
    proposal = _find(Manage(seeded).proposals(), PROPOSAL_SUPERSEDE)
    Manage(seeded).decide(proposal.id, accept=True)
    assert len(seeded.records(include_archived=True)) == before


def test_rejecting_a_proposal_changes_no_memory_file(seeded):
    _twins(seeded)
    before = {record.name: record.to_text() for record in seeded.records()}
    proposal = _find(Manage(seeded).proposals(), PROPOSAL_SUPERSEDE)
    Manage(seeded).decide(proposal.id, accept=False)
    assert {record.name: record.to_text() for record in seeded.records()} == before


def test_a_cluster_proposal_cannot_be_accepted_below_human_authority(seeded):
    for index in range(seeded.config.manage.cluster_min_files):
        seeded.record(
            abstract=f"Kubernetes upgrade note {index} about the kubernetes control plane",
            type="reference",
            domain="reference",
            body="Body.",
            name=f"kubernetes-upgrade-note-{index}",
        )
    proposal = _find(Manage(seeded).proposals(), PROPOSAL_CLUSTER)
    with pytest.raises(AuthorityError):
        Manage(seeded).decide(proposal.id, accept=True)


def test_deciding_an_unknown_proposal_is_refused(seeded):
    with pytest.raises(NotFoundError):
        Manage(seeded).decide("not-a-proposal", accept=True)


def test_the_decision_ledger_survives_an_index_rebuild(seeded):
    _twins(seeded)
    proposal = _find(Manage(seeded).proposals(), PROPOSAL_SUPERSEDE)
    Manage(seeded).decide(proposal.id, accept=False)
    shutil.rmtree(seeded.layout.index_dir)
    seeded.rebuild_index()
    assert proposal.id not in {open_one.id for open_one in Manage(seeded).proposals()}


def test_one_read_is_settled_once_however_many_sleeps_follow(seeded):
    seeded.read("staging-deploy-e4021")
    Manage(seeded).sleep()
    settled = seeded.find("staging-deploy-e4021").weight
    Manage(seeded).sleep()
    Manage(seeded).sleep()
    assert seeded.find("staging-deploy-e4021").weight == settled


def test_a_read_between_two_sleeps_raises_the_weight_again(seeded, clock):
    seeded.read("staging-deploy-e4021")
    Manage(seeded).sleep()
    settled = seeded.find("staging-deploy-e4021").weight
    clock.advance(hours=1)
    seeded.read("staging-deploy-e4021")
    Manage(seeded).sleep()
    assert seeded.find("staging-deploy-e4021").weight > settled


def test_a_sleep_with_no_new_reads_settles_no_weight(seeded):
    seeded.read("staging-deploy-e4021")
    Manage(seeded).sleep()
    assert ACTION_WEIGHT_SETTLED not in _kinds(Manage(seeded).sleep())


def _flat_topic(store, count, abstract):
    for index in range(count):
        store.record(
            abstract=abstract.format(index=index),
            type="reference",
            domain="reference",
            body="Body.",
            name=f"topic-note-{index}",
        )


def test_one_group_proposes_one_cluster_however_many_tokens_it_shares(seeded):
    _flat_topic(
        seeded,
        seeded.config.manage.cluster_min_files,
        "Kubernetes control plane upgrade note {index}",
    )
    clusters = [
        proposal for proposal in Manage(seeded).proposals() if proposal.kind == PROPOSAL_CLUSTER
    ]
    assert len(clusters) == 1


def test_a_group_sharing_too_few_tokens_is_not_a_topic(seeded):
    seeded.config.manage.cluster_min_shared_tokens = 99
    _flat_topic(
        seeded,
        seeded.config.manage.cluster_min_files,
        "Kubernetes control plane upgrade note {index}",
    )
    assert not [
        proposal for proposal in Manage(seeded).proposals() if proposal.kind == PROPOSAL_CLUSTER
    ]
