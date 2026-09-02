"""Invariant 4 has a retrieval half: raw material that no query can reach is not a backstop."""

import pytest
from agent_memory.core.recall import Recall

TRANSCRIPT = (
    "user: I finally watched that documentary you recommended, Seaspiracy, on 2026-01-04.\n"
    "assistant: Glad you got to it. The follow-up I mentioned was 'My Octopus Teacher'.\n"
    "user: Right, and the ticket for the aquarium talk was 42 dollars.\n"
)


@pytest.fixture
def with_raw(store):
    store.record(
        abstract="Watches nature documentaries and discusses them afterwards",
        type="preference",
        domain="user",
        name="nature-documentaries",
    )
    store.archive.append_session("session-alpha", TRANSCRIPT)
    store.sync_index()
    return store


def test_default_recall_never_returns_raw_material(with_raw):
    hits = Recall(with_raw).recall("octopus teacher aquarium ticket")
    assert all(hit.source == "memory" for hit in hits)
    assert not [hit for hit in hits if "octopus" in hit.abstract.lower()]


def test_deep_recall_reaches_a_fact_the_distiller_never_wrote_down(with_raw):
    hits = Recall(with_raw).recall("My Octopus Teacher follow-up recommendation", deep=True)
    raw = [hit for hit in hits if hit.source == "raw"]
    assert raw
    assert "Octopus" in raw[0].abstract


def test_raw_hits_carry_a_path_and_rank_below_distilled_memory(with_raw):
    with_raw.record(
        abstract="The aquarium talk ticket cost 42 dollars on 2026-01-04",
        type="fact",
        domain="user",
        name="aquarium-ticket-price",
    )
    hits = Recall(with_raw).recall("aquarium talk ticket 42 dollars", deep=True)
    assert hits[0].source == "memory"
    raw = [hit for hit in hits if hit.source == "raw"]
    assert raw
    assert raw[0].path.endswith(".txt")
    assert raw[0].score < hits[0].score


def test_raw_material_survives_an_index_rebuild(with_raw):
    query = "My Octopus Teacher follow-up recommendation"
    before = {hit.name for hit in Recall(with_raw).recall(query, deep=True)}
    with_raw.layout.index_db.unlink()
    with_raw.rebuild_index()
    assert {hit.name for hit in Recall(with_raw).recall(query, deep=True)} == before


def test_indexing_raw_material_does_not_write_to_it(with_raw):
    path = with_raw.layout.sessions / "session-alpha.txt"
    before = path.read_bytes()
    Recall(with_raw).recall("octopus", deep=True)
    with_raw.sync_index()
    assert path.read_bytes() == before


def test_deep_widens_the_list_so_raw_material_is_not_crowded_out(with_raw):
    for index in range(with_raw.config.recall.default_limit):
        with_raw.record(
            abstract=f"Nature documentary note number {index} about octopus and aquarium visits",
            type="fact",
            domain="user",
            name=f"documentary-note-{index}",
        )
    shallow = Recall(with_raw).recall("octopus aquarium documentary")
    deep = Recall(with_raw).recall("octopus aquarium documentary", deep=True)

    assert len(shallow) == with_raw.config.recall.default_limit
    assert len(deep) > len(shallow)
    assert [hit for hit in deep if hit.source == "raw"]
