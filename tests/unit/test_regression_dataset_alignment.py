import json

import pytest
from agent_memory.harness import dataset


def test_dataset_session_arrays_must_align(tmp_path):
    entry = {
        "question_id": "q1",
        "question": "Fixture",
        "answer": "Fixture",
        "question_type": "single",
        "haystack_session_ids": ["s1", "s2"],
        "haystack_dates": ["2026-01-01"],
        "haystack_sessions": [
            [{"role": "user", "content": "first"}],
            [{"role": "user", "content": "lost evidence"}],
        ],
        "answer_session_ids": ["s2"],
    }
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps([entry]))
    with pytest.raises(ValueError):
        dataset.load(path)
