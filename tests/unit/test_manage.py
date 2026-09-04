"""M6 — unattended Manage adds and amends; anything that loses a distinction is a proposal."""

import shutil
import subprocess

import pytest
from agent_memory.core.errors import NotFoundError
from agent_memory.core.manage import (
    ACTION_CLUSTERED,
    ACTION_DUPLICATE_MERGED,
    ACTION_GROUP_MERGED,
    ACTION_LINK_ADDED,
    ACTION_REDISTILL_REQUESTED,
    ACTION_WEIGHT_SETTLED,
    PROPOSAL_DELETE,
    PROPOSAL_MERGE,
    PROPOSAL_SPLIT,
    PROPOSAL_SUPERSEDE,
    Manage,
)
from agent_memory.core.pending import Pending
from agent_memory.core.recall import Recall


def _kinds(report):
    return {action.kind for action in report.actions}


def _proposal_kinds(report):
    return {proposal.kind for proposal in report.proposals}


def test_unattended_sleep_never_shrinks_the_store(seeded):
    before = len(seeded.records(include_invalid=True))
    Manage(seeded).sleep()
    Manage(seeded).sleep()
    assert len(seeded.records(include_invalid=True)) >= before


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


def test_exact_duplicates_are_merged_by_supersede_not_by_deletion(seeded):
    original = seeded.find("file-truth-invariant")
    seeded.record(
        abstract=original.abstract,
        type=original.type,
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
        name="ryan-concise-restated",
    )
    report = Manage(seeded).sleep()
    assert {PROPOSAL_MERGE, PROPOSAL_SUPERSEDE} & _proposal_kinds(report)
    assert seeded.find("ryan-concise-restated") is not None
    assert seeded.find("ryan-prefers-concise-answers") is not None


def test_a_crowded_directory_is_clustered_into_a_new_group_without_a_ruling(store):
    for index in range(store.config.manage.cluster_min_files):
        store.record(
            abstract=f"Deploy pipeline note number {index} about the release rollout",
            type="procedure",
            name=f"deploy-note-{index}",
        )
    before = {record.name: (record.body, record.provenance) for record in store.records()}
    report = Manage(store).sleep()
    moved = [action for action in report.actions if action.kind == ACTION_CLUSTERED]
    assert {action.target for action in moved} == set(before)
    parents = {record.path.parent for record in store.records()}
    assert len(parents) == 1
    assert parents != {store.layout.type_dir("procedure") / store.config.storage.default_project}
    assert {r.name: (r.body, r.provenance) for r in store.records()} == before
    assert Recall(store).recall("release rollout")


def test_group_directories_that_differ_only_in_spelling_are_merged(store):
    store.record(
        type="preference",
        fields={"topic": "coffee", "subject": "milk"},
        abstract="Prefers oat milk",
        create_group=True,
    )
    store.record(
        type="preference",
        fields={"topic": "coffee", "subject": "roast"},
        abstract="Prefers a dark roast",
        create_group=True,
    )
    store.record(
        type="preference",
        fields={"topic": "Coffees", "subject": "cup"},
        abstract="Prefers a large cup",
        create_group=True,
    )
    report = Manage(store).sleep()
    merged = [action for action in report.actions if action.kind == ACTION_GROUP_MERGED]
    assert [action.target for action in merged] == ["cup"]
    assert store.layout.groups_of("preference") == {"coffee"}
    assert store.find("cup").fields["topic"] == "coffee"


def test_raw_material_hit_repeatedly_but_cited_by_nothing_is_sent_back_to_the_still(store):
    store.archive.append_session("chat", ["user: the queue timeout is 30 seconds now"])
    store.rebuild_index()
    for _ in range(store.config.manage.raw_hit_min):
        Recall(store).recall("queue timeout", deep=True)
    report = Manage(store).sleep()
    assert ACTION_REDISTILL_REQUESTED in _kinds(report)
    requested = Pending(store.layout).redistill("chat")
    assert requested and requested[0].session == "chat"
    assert ACTION_REDISTILL_REQUESTED not in _kinds(Manage(store).sleep())


def test_raw_material_already_cited_is_not_sent_back(store):
    pointer = store.archive.append_session("chat", ["user: the queue timeout is 30 seconds now"])
    store.record(
        type="fact",
        fields={"subject": "queue timeout"},
        abstract="Queue timeout is 30 seconds",
        provenance=["sessions/chat#0-0"],
    )
    for _ in range(store.config.manage.raw_hit_min):
        Recall(store).recall("queue timeout", deep=True)
    assert ACTION_REDISTILL_REQUESTED not in _kinds(Manage(store).sleep())
    assert pointer is not None


def test_a_file_with_sections_from_several_conversations_becomes_a_split_proposal(store):
    body = "\n".join(f"## part {index}\n\ntext {index}" for index in range(3))
    store.record(
        type="fact",
        fields={"subject": "two things"},
        abstract="Two things at once",
        body=body,
        provenance=["sessions/a#0-0", "sessions/b#0-0"],
    )
    proposals = Manage(store).proposals()
    assert [p.kind for p in proposals if p.targets == ("two-things",)] == [PROPOSAL_SPLIT]


def test_a_memory_at_the_floor_that_nobody_recalled_becomes_a_delete_proposal(store):
    store.record(
        type="fact",
        fields={"subject": "forgotten"},
        abstract="Nobody asks about this",
        weight=store.config.weight.floor,
    )
    proposals = Manage(store).proposals()
    assert [p.kind for p in proposals if p.targets == ("forgotten",)] == [PROPOSAL_DELETE]
    Manage(store).decide(next(p for p in proposals if p.kind == PROPOSAL_DELETE).id, accept=True)
    assert not store.find("forgotten").is_active()
    assert store.find("forgotten").path.exists()


def test_after_any_sleep_the_files_on_disk_never_shrink(seeded):
    _twins(seeded)
    before = len(seeded.records(include_invalid=True))
    for proposal in Manage(seeded).proposals():
        try:
            Manage(seeded).decide(proposal.id, accept=True)
        except Exception:
            continue
    Manage(seeded).sleep()
    assert len(seeded.records(include_invalid=True)) >= before


def test_gc_is_the_only_road_to_physical_removal(seeded):
    thin, rich = _twins(seeded)
    proposal = _find(Manage(seeded).proposals(), PROPOSAL_SUPERSEDE)
    Manage(seeded).decide(proposal.id, accept=True)
    invalid_path = seeded.find(thin).path
    assert invalid_path.exists()
    assert seeded.gc() == [thin]
    assert not invalid_path.exists()
    assert seeded.find(rich).is_active()


def test_a_sleep_inside_a_repository_leaves_one_commit(seeded):
    subprocess.run(["git", "init", "-q", str(seeded.root)], check=True)
    subprocess.run(
        ["git", "-C", str(seeded.root), "config", "user.email", "t@example.com"], check=True
    )
    subprocess.run(["git", "-C", str(seeded.root), "config", "user.name", "t"], check=True)
    report = Manage(seeded).sleep()
    assert report.committed
    log = subprocess.run(
        ["git", "-C", str(seeded.root), "log", "--oneline"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert len(log.splitlines()) == 1
    assert "sleep" in log


def test_a_sleep_outside_a_repository_commits_nothing_and_says_so(seeded):
    assert Manage(seeded).sleep().committed is False


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


def _twins(store):
    store.record(
        abstract="The nightly export job times out against the reporting replica",
        type="experience",
        body="Short note.",
        name="nightly-export-timeout",
    )
    store.record(
        abstract="The nightly export job times out against the reporting replica again",
        type="experience",
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
    before = len(seeded.records(include_invalid=True))
    proposal = _find(Manage(seeded).proposals(), PROPOSAL_SUPERSEDE)
    Manage(seeded).decide(proposal.id, accept=True)
    assert len(seeded.records(include_invalid=True)) == before


def test_rejecting_a_proposal_changes_no_memory_file(seeded):
    _twins(seeded)
    before = {record.name: record.to_text() for record in seeded.records()}
    proposal = _find(Manage(seeded).proposals(), PROPOSAL_SUPERSEDE)
    Manage(seeded).decide(proposal.id, accept=False)
    assert {record.name: record.to_text() for record in seeded.records()} == before


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
            body="Body.",
            name=f"topic-note-{index}",
        )


def test_one_group_moves_into_one_directory_however_many_tokens_it_shares(seeded):
    _flat_topic(
        seeded,
        seeded.config.manage.cluster_min_files,
        "Kubernetes control plane upgrade note {index}",
    )
    report = Manage(seeded).sleep()
    moved = [action for action in report.actions if action.kind == ACTION_CLUSTERED]
    assert len(moved) == seeded.config.manage.cluster_min_files
    assert len({action.detail for action in moved}) == 1


def test_a_group_sharing_too_few_tokens_is_not_a_topic(seeded):
    seeded.config.manage.cluster_min_shared_tokens = 99
    _flat_topic(
        seeded,
        seeded.config.manage.cluster_min_files,
        "Kubernetes control plane upgrade note {index}",
    )
    assert ACTION_CLUSTERED not in _kinds(Manage(seeded).sleep())
