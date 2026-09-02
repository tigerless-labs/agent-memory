"""The fixed exam exists to make memory configurations comparable.

The agentic exam folds the host's own search behaviour into every score; repeated replays of a
frozen configuration moved by +/-7 answers per 120 episodes. Here the harness retrieves, so the
context a configuration produces is a deterministic function of that configuration.
"""

import pytest
from agent_memory.core.recall import Recall
from agent_memory.harness import exam
from agent_memory.harness.framing import fixed_exam


@pytest.fixture
def stocked(seeded):
    seeded.archive.append_session(
        "session-one",
        "user: the aquarium talk ticket was 42 dollars on 2026-01-04\n"
        "assistant: noted, that is cheaper than last year\n",
    )
    seeded.sync_index()
    return seeded


def test_the_same_store_and_question_always_build_the_same_context(stocked):
    first = exam.build_context(stocked, "deploy drain queue", full_text_entries=2)
    second = exam.build_context(stocked, "deploy drain queue", full_text_entries=2)
    assert first == second
    assert first.entries > 0


def test_the_context_carries_full_text_for_the_leading_entries_only(stocked):
    narrow = exam.build_context(stocked, "deploy drain queue lease", full_text_entries=0)
    wide = exam.build_context(stocked, "deploy drain queue lease", full_text_entries=3)
    assert "Raise drain_timeout" not in narrow.text
    assert "Raise drain_timeout" in wide.text
    assert narrow.entries == wide.entries


def test_the_list_width_knob_changes_the_context_it_produces(stocked):
    for index in range(stocked.config.recall.default_limit * 2):
        stocked.record(
            abstract=f"Deploy note number {index} about the drain window and the queue",
            type="experience", domain="experience", name=f"deploy-note-{index}",
        )
    narrow = exam.build_context(stocked, "deploy drain window queue", full_text_entries=0)
    stocked.config.recall.default_limit *= 2
    wide = exam.build_context(stocked, "deploy drain window queue", full_text_entries=0)
    assert wide.entries > narrow.entries


def test_the_raw_fallback_knob_reaches_material_no_entry_holds(stocked):
    stocked.config.recall.raw_enabled = True
    reached = exam.build_context(stocked, "aquarium talk ticket 42 dollars", full_text_entries=0)
    stocked.config.recall.raw_enabled = False
    withheld = exam.build_context(stocked, "aquarium talk ticket 42 dollars", full_text_entries=0)
    assert "42 dollars" in reached.text
    assert "42 dollars" not in withheld.text


def test_an_empty_store_produces_a_context_that_says_so(store):
    context = exam.build_context(store, "anything at all", full_text_entries=2)
    assert context.is_empty()
    assert exam.NOTHING_FOUND in context.text


def test_the_fixed_prompt_carries_the_context_and_the_question(stocked, seeded):
    from agent_memory.harness import dataset

    episode = dataset.Episode(
        id="q1", question="What must the drain window exceed?", answer="the lease TTL",
        question_type="single-session-user", question_date="2026/02/01",
        sessions=(), evidence_session_ids=(),
    )
    context = exam.build_context(stocked, episode.question, full_text_entries=2)
    prompt = fixed_exam(episode, context.text)
    assert episode.question in prompt
    assert context.text in prompt


def test_recall_still_never_mutates_truth_when_the_harness_drives_it(stocked):
    import hashlib

    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in stocked.layout.truth_files()}
    exam.build_context(stocked, "deploy drain queue", full_text_entries=3)
    after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in stocked.layout.truth_files()}
    assert after == before
    assert Recall(stocked).recall("deploy drain queue")
