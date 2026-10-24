from agent_memory.core import sessions


def test_blank_messages_keep_append_ranges_contiguous(store):
    pointer = store.archive.append_session("session", ["user: alpha", "", "assistant: beta"])
    assert pointer is not None
    messages = sessions.resolve(store.layout, pointer)
    assert [item.index for item in messages] == [0, 1, 2]
    assert [item.text for item in messages] == ["alpha", "", "beta"]
    following = store.archive.append_session("session", ["user: gamma"])
    assert following is not None
    assert following.start == pointer.end + 1
