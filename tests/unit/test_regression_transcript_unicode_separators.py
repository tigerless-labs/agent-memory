import json

import pytest
from agent_memory.adapters import transcript

SEPARATORS = ["\N{LINE SEPARATOR}", "\N{PARAGRAPH SEPARATOR}", "\x85"]


def _write(path, rows):
    text = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n"
    path.write_text(text, encoding="utf-8")


@pytest.mark.parametrize("separator", SEPARATORS, ids=["u2028", "u2029", "u0085"])
def test_claude_transcript_keeps_unicode_separators_inside_one_message(tmp_path, separator):
    text = "before" + separator + "after"
    path = tmp_path / "session.jsonl"
    _write(
        path,
        [
            {"type": "user", "message": {"role": "user", "content": "hello"}},
            {"type": "assistant", "message": {"role": "assistant", "content": text}},
        ],
    )
    assert transcript.items(path, host="claude-code") == ["user: hello", f"assistant: {text}"]


@pytest.mark.parametrize("separator", SEPARATORS, ids=["u2028", "u2029", "u0085"])
def test_muse_session_keeps_unicode_separators_inside_one_message(tmp_path, separator):
    text = "before" + separator + "after"
    path = tmp_path / "session.jsonl"
    _write(
        path,
        [
            {"payload": {"event": {"kind": "started", "prompt": text}, "kind": "run"}},
            {"payload": {"event": {"role": "assistant", "text": "ok"}}},
        ],
    )
    assert transcript.items(path, host="muse-code") == [f"user: {text}", "assistant: ok"]
