import pytest
from agent_memory.core.errors import ValidationError
from agent_memory.core.sessions import render_pointer


def test_correction_cannot_date_a_fact_after_its_cited_evidence(store, clock):
    pointer = store.archive.append_session("session", ["user: The aquarium closes on Monday"])
    assert pointer is not None
    record = store.record(
        abstract="Aquarium closes on Monday",
        type="fact",
        body="Monday",
        name="aquarium-hours",
        provenance=[render_pointer(pointer)],
    )
    assert record.path is not None
    before = record.path.read_bytes()
    archived_before = {p: p.read_bytes() for p in store.layout.archive.rglob("*") if p.is_file()}
    clock.advance(days=1)
    with pytest.raises(ValidationError):
        store.correct(
            record.name, valid_from=clock.timestamp(), provenance=["new synthetic excerpt"]
        )
    assert record.path.read_bytes() == before
    assert {
        p: p.read_bytes() for p in store.layout.archive.rglob("*") if p.is_file()
    } == archived_before
