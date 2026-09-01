"""M3 — eligibility before relevance; reads never touch truth."""

import hashlib

from agent_memory.core.access_log import AccessLog
from agent_memory.core.database import Database
from agent_memory.core.recall import Recall
from agent_memory.core.store import LEVEL_ABSTRACT, LEVEL_OUTLINE


def _names(hits):
    return [hit.name for hit in hits]


def test_literal_tokens_such_as_error_codes_are_retrievable(seeded):
    hits = Recall(seeded).recall("E4021")
    assert "staging-deploy-e4021" in _names(hits)


def test_paraphrase_of_the_abstract_retrieves_the_record(seeded):
    hits = Recall(seeded).recall("deploy fails when the queue drains")
    assert "staging-deploy-e4021" in _names(hits)


def test_superseded_records_are_excluded_before_relevance_is_considered(seeded):
    seeded.record(
        abstract="The staging deploy now fails with error E4021 only under load",
        type="experience",
        domain="experience",
        name="staging-deploy-e4021-under-load",
        valid_from="2026-01-10",
    )
    seeded.correct("staging-deploy-e4021", supersede_with="staging-deploy-e4021-under-load")

    hits = Recall(seeded).recall("E4021")
    assert "staging-deploy-e4021" not in _names(hits)
    assert "staging-deploy-e4021-under-load" in _names(hits)


def test_as_of_walks_back_up_the_supersede_chain(seeded):
    seeded.record(
        abstract="The staging deploy now fails with error E4021 only under load",
        type="experience",
        domain="experience",
        name="staging-deploy-e4021-under-load",
        valid_from="2026-02-01",
    )
    seeded.correct("staging-deploy-e4021", supersede_with="staging-deploy-e4021-under-load")

    before = Recall(seeded).recall("E4021", as_of="2026-01-20")
    after = Recall(seeded).recall("E4021", as_of="2026-02-05")
    assert "staging-deploy-e4021" in _names(before)
    assert "staging-deploy-e4021-under-load" not in _names(before)
    assert "staging-deploy-e4021-under-load" in _names(after)


def test_deep_is_the_only_way_into_the_archive(seeded):
    seeded.retire("staging-deploy-e4021")
    assert "staging-deploy-e4021" not in _names(Recall(seeded).recall("E4021"))
    assert "staging-deploy-e4021" in _names(Recall(seeded).recall("E4021", deep=True))


def test_scope_restricts_by_path_prefix(seeded):
    hits = Recall(seeded).recall("deploy queue drain answers", scope="experience")
    assert hits
    assert {hit.domain for hit in hits} == {"experience"}


def test_l0_entries_carry_the_full_contract(seeded):
    hit = Recall(seeded).recall("E4021")[0]
    payload = hit.as_dict()
    for key in ("name", "path", "abstract", "anchor", "score", "weight", "relevance", "recency"):
        assert key in payload
    assert hit.score > 0


def test_weight_reorders_two_otherwise_comparable_hits(seeded):
    seeded.record(
        abstract="Deploy notes for the drain window, second copy",
        type="experience",
        domain="experience",
        name="drain-notes-b",
    )
    seeded.record(
        abstract="Deploy notes for the drain window, first copy",
        type="experience",
        domain="experience",
        name="drain-notes-a",
    )
    baseline = _names(Recall(seeded).recall("deploy notes drain window"))
    seeded.feedback("drain-notes-b", seeded.config.weight.boost_step)
    boosted = _names(Recall(seeded).recall("deploy notes drain window"))
    assert boosted.index("drain-notes-b") <= baseline.index("drain-notes-b")


def test_recall_writes_the_access_log_and_leaves_truth_bytes_untouched(seeded):
    before = {
        path: hashlib.sha256(path.read_bytes()).hexdigest() for path in seeded.layout.truth_files()
    }
    hits = Recall(seeded).recall("deploy queue drain")
    seeded.read("staging-deploy-e4021", level=LEVEL_ABSTRACT)
    after = {
        path: hashlib.sha256(path.read_bytes()).hexdigest() for path in seeded.layout.truth_files()
    }
    assert after == before

    with Database(seeded.layout).connect() as connection:
        entries = AccessLog(connection).entries()
    assert len(entries) >= len(hits) + 1


def test_limit_is_respected(seeded):
    assert len(Recall(seeded).recall("deploy queue drain answers memory", limit=1)) == 1


def test_progressive_disclosure_levels_cost_more_the_deeper_they_go(seeded):
    abstract = seeded.read("staging-deploy-e4021", level=LEVEL_ABSTRACT)
    outline = seeded.read("staging-deploy-e4021", level=LEVEL_OUTLINE)
    full = seeded.read("staging-deploy-e4021")
    assert outline.outline == ("Symptom", "Cause", "Fix")
    assert len(abstract.text) < len(full.text)
    assert len(outline.text) < len(full.text)


def test_a_hit_in_a_long_body_carries_the_section_anchor(seeded):
    hits = Recall(seeded).recall("lease TTL drain timeout infra queue yaml")
    hit = next(hit for hit in hits if hit.name == "staging-deploy-e4021")
    assert hit.anchor == "fix"
