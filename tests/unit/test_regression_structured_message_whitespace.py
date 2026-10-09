from agent_memory.core import sessions


def test_structured_raw_code_keeps_indentation_and_trailing_whitespace(store):
    text = "    return synthetic_fixture  \n"
    pointer = store.archive.append_session("whitespace", [{"role": "user", "text": text}])
    messages = sessions.resolve(store.layout, pointer)
    assert messages[0].text == text
    assert sessions.read(store.layout, "whitespace")[0].text == text
