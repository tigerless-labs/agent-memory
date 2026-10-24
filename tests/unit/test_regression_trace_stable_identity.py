from agent_memory.core import sessions


def test_trace_keeps_stored_identity_after_a_truth_file_is_renamed(store):
    pointer = store.archive.append_session("session", ["user: evidence"])
    assert pointer is not None
    record = store.record(
        abstract="Useful evidence fact",
        type="fact",
        name="stable-memory",
        provenance=[sessions.render_pointer(pointer)],
    )
    assert record.path is not None
    renamed = record.path.with_name("renamed-file.md")
    record.path.rename(renamed)
    store.rebuild_index()
    assert store.find(record.name).path == renamed
    assert [message.text for message in store.trace(record.name)] == ["evidence"]
