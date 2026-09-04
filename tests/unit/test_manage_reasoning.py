"""The reasoning pass: judgement is borrowed, authority is not."""

import json

import pytest
from agent_memory.core.manage import (
    PROPOSAL_ABSTRACT_REVIEW,
    PROPOSAL_SUPERSEDE,
    TIER_PROPOSAL,
    TIER_UNATTENDED,
    Manage,
)
from agent_memory.core.reasoning import parse, render


class Recorder:
    """A reasoner that answers from a script and keeps the prompt it was given."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.prompts = []

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.replies.pop(0) if self.replies else ""


def _twins(store):
    store.record(
        abstract="The drain window closes before the worker lease expires",
        type="experience",
        body="Short.",
        name="drain-window-first",
    )
    store.record(
        abstract="The drain window closes before the worker lease expires again",
        type="experience",
        body="Longer body carrying the lease TTL and the fix that worked.",
        name="drain-window-second",
    )


def _open(store, kind):
    return [proposal for proposal in Manage(store).proposals() if proposal.kind == kind]


def _verdict(proposal_id, verdict, text=""):
    line = {"proposal": proposal_id, "verdict": verdict}
    if text:
        line["text"] = text
    return json.dumps(line)


def test_the_prompt_carries_every_open_proposal_and_the_entries_it_names(seeded):
    _twins(seeded)
    reasoner = Recorder("")
    Manage(seeded).sleep(reasoner=reasoner)
    prompt = reasoner.prompts[0]
    for proposal in _open(seeded, PROPOSAL_SUPERSEDE):
        assert proposal.id in prompt
        for target in proposal.targets:
            assert target in prompt


def test_an_unreadable_reply_changes_nothing(seeded):
    _twins(seeded)
    before = {record.name: record.to_text() for record in seeded.records()}
    report = Manage(seeded).sleep(reasoner=Recorder("I would merge the first two, I think."))
    assert {record.name: record.to_text() for record in seeded.records()} == before
    assert not report.decisions


def test_a_verdict_on_an_unknown_proposal_is_ignored(seeded):
    _twins(seeded)
    report = Manage(seeded).sleep(reasoner=Recorder(_verdict("0123456789ab", "accept")))
    assert not report.decisions
    assert _open(seeded, PROPOSAL_SUPERSEDE)


def test_unattended_authority_withholds_a_supersede_and_leaves_it_open(seeded):
    _twins(seeded)
    seeded.config.manage.authority = TIER_UNATTENDED
    proposal = _open(seeded, PROPOSAL_SUPERSEDE)[0]
    report = Manage(seeded).sleep(reasoner=Recorder(_verdict(proposal.id, "accept")))
    assert proposal.id in report.withheld
    assert seeded.find("drain-window-first").is_active()
    assert proposal.id in {open_one.id for open_one in Manage(seeded).proposals()}


def test_confirmed_authority_applies_the_same_supersede(seeded):
    _twins(seeded)
    seeded.config.manage.authority = TIER_PROPOSAL
    proposal = _open(seeded, PROPOSAL_SUPERSEDE)[0]
    report = Manage(seeded).sleep(reasoner=Recorder(_verdict(proposal.id, "accept")))
    assert [decision.proposal_id for decision in report.decisions] == [proposal.id]
    assert seeded.find("drain-window-first").superseded_by == "drain-window-second"


def test_an_abstract_rewrite_needs_no_escalation(seeded):
    seeded.record(
        abstract="Thin",
        type="fact",
        body="The release pipeline refuses tags that are not signed.",
        name="thin-abstract-entry",
    )
    seeded.config.manage.authority = TIER_UNATTENDED
    proposal = next(
        proposal
        for proposal in _open(seeded, PROPOSAL_ABSTRACT_REVIEW)
        if proposal.targets == ("thin-abstract-entry",)
    )
    replacement = "The release pipeline refuses unsigned tags"
    Manage(seeded).sleep(
        reasoner=Recorder(_verdict(proposal.id, "accept", replacement))
    )
    assert seeded.find("thin-abstract-entry").abstract == replacement


def test_a_rejection_closes_the_proposal_without_touching_a_file(seeded):
    _twins(seeded)
    before = {record.name: record.to_text() for record in seeded.records()}
    proposal = _open(seeded, PROPOSAL_SUPERSEDE)[0]
    report = Manage(seeded).sleep(reasoner=Recorder(_verdict(proposal.id, "reject")))
    assert [decision.verdict for decision in report.decisions] == ["rejected"]
    assert {record.name: record.to_text() for record in seeded.records()} == before
    assert proposal.id not in {open_one.id for open_one in Manage(seeded).proposals()}


def test_a_reply_wrapped_in_a_code_fence_is_still_read(seeded):
    _twins(seeded)
    seeded.config.manage.authority = TIER_PROPOSAL
    proposal = _open(seeded, PROPOSAL_SUPERSEDE)[0]
    fenced = "```json\n" + _verdict(proposal.id, "reject") + "\n```"
    report = Manage(seeded).sleep(reasoner=Recorder(fenced))
    assert [decision.proposal_id for decision in report.decisions] == [proposal.id]


@pytest.mark.parametrize(
    "reply",
    ["", "[]", "null", '{"proposal": null, "verdict": "accept"}', '{"verdict": "accept"}'],
)
def test_every_shape_of_empty_reply_is_survivable(seeded, reply):
    _twins(seeded)
    assert not Manage(seeded).sleep(reasoner=Recorder(reply)).decisions


def test_rendering_and_parsing_are_inverse_enough_to_round_trip(seeded):
    _twins(seeded)
    proposals = Manage(seeded).proposals()
    prompt = render(proposals, seeded.records())
    assert all(proposal.id in prompt for proposal in proposals)
    replies = "\n".join(_verdict(proposal.id, "reject") for proposal in proposals)
    assert [verdict.proposal_id for verdict in parse(replies)] == [
        proposal.id for proposal in proposals
    ]
