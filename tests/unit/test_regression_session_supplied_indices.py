from agent_memory.core import sessions


def test_host_indices_cannot_redirect_archived_provenance(store):
    pointer = store.archive.append_session(
        "session", [{"index": 100, "text": "alpha"}, {"index": -7, "text": "beta"}]
    )
    assert pointer is not None
    messages = sessions.resolve(store.layout, pointer)
    assert [message.index for message in messages] == [0, 1]
    assert [message.text for message in messages] == ["alpha", "beta"]
    assert sessions.read(store.layout, "session") == messages
