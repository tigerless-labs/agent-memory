"""Invariant 4's other half: every memory can point at the exact messages it came from."""

import pytest
from agent_memory.adapters import capture as capture_module
from agent_memory.core import sessions
from agent_memory.core.errors import ValidationError
from agent_memory.core.recall import Recall

LINES = [
    "user: I finally watched Seaspiracy on 2026-01-04, the one you recommended.",
    "assistant: Glad you got to it. The follow-up I mentioned was 'My Octopus Teacher'.",
    "user: Right, and the ticket for the aquarium talk was 42 dollars.",
]


def test_appending_a_session_numbers_messages_from_where_the_last_append_stopped(store):
    first = store.archive.append_session("s1", LINES[:2])
    second = store.archive.append_session("s1", LINES[2:])
    assert (first.start, first.end) == (0, 1)
    assert (second.start, second.end) == (2, 2)
    messages = sessions.read(store.layout, "s1")
    assert [message.index for message in messages] == [0, 1, 2]
    assert messages[1].role == "assistant"
    assert "Octopus" in messages[1].text
    assert all(message.at for message in messages)


def test_a_pointer_renders_and_parses_to_the_same_range():
    pointer = sessions.Pointer("s1", 3, 7)
    assert sessions.parse_pointer(sessions.render_pointer(pointer)) == pointer
    assert sessions.parse_pointer("archive/provenance/x/y.md") is None


def test_a_pointer_survives_rechunking_of_the_raw_index(store):
    store.archive.append_session("s2", LINES)
    pointer = sessions.Pointer("s2", 1, 1)
    before = [message.text for message in sessions.resolve(store.layout, pointer)]
    store.config.index.raw_chunk_chars = len(LINES[0])
    store.rebuild_index()
    after = [message.text for message in sessions.resolve(store.layout, pointer)]
    assert before == after
    assert "Octopus" in after[0]


def test_a_record_may_cite_a_message_range_and_the_pointer_is_kept_verbatim(store):
    appended = store.archive.append_session("s3", LINES)
    pointer = sessions.render_pointer(appended)
    written = store.record(
        type="event",
        fields={"subject": "seaspiracy"},
        abstract="Watched Seaspiracy",
        provenance=[pointer],
    )
    assert pointer in written.provenance
    traced = store.trace(written.name)
    assert [message.index for message in traced] == [0, 1, 2]


def test_provenance_never_shrinks_through_an_update_or_a_replacement(store):
    appended = store.archive.append_session("s4", LINES)
    pointer = sessions.render_pointer(sessions.Pointer("s4", 0, 0))
    later = sessions.render_pointer(sessions.Pointer("s4", 2, 2))
    store.record(
        type="fact",
        fields={"subject": "ticket"},
        abstract="Ticket was 42 dollars",
        provenance=[pointer],
    )
    updated = store.record(
        type="fact",
        fields={"subject": "ticket"},
        abstract="Aquarium ticket: 42 dollars",
        provenance=[later],
    )
    assert set(updated.provenance) >= {pointer, later}
    successor = store.record(
        type="fact",
        fields={"subject": "ticket v2"},
        abstract="Ticket is now 50 dollars",
        supersedes=updated.name,
        provenance=[sessions.render_pointer(appended)],
    )
    assert set(store.find(updated.name).provenance) >= {pointer, later}
    assert successor.provenance and successor.provenance != updated.provenance


def test_a_fact_dated_after_its_evidence_is_rejected(store, clock):
    appended = store.archive.append_session("s5", LINES)
    with pytest.raises(ValidationError) as raised:
        store.record(
            type="fact",
            fields={"subject": "future"},
            abstract="Dated after the conversation",
            valid_from="2030-01-01",
            provenance=[sessions.render_pointer(appended)],
        )
    assert "valid_from" in {error.field for error in raised.value.errors}


def test_deep_hits_say_which_memories_already_cite_them(store):
    appended = store.archive.append_session("s6", LINES)
    store.record(
        type="event",
        fields={"subject": "octopus"},
        abstract="Follow-up film was My Octopus Teacher",
        provenance=[sessions.render_pointer(sessions.Pointer("s6", 1, 1))],
    )
    store.sync_index()
    raw = [hit for hit in Recall(store).recall("Octopus Teacher", deep=True) if hit.source == "raw"]
    assert raw
    assert "octopus" in raw[0].cited_by
    assert sessions.parse_pointer(raw[0].name).session == appended.session


def test_capture_archives_the_increment_as_numbered_messages_and_returns_its_pointer(store):
    result = capture_module.capture(store, "hooked", LINES)
    pointer = sessions.parse_pointer(result.pointer)
    assert pointer is not None
    assert (pointer.start, pointer.end) == (0, len(LINES) - 1)
    assert [message.text for message in sessions.resolve(store.layout, pointer)] == [
        line.split(": ", 1)[1] for line in LINES
    ]
