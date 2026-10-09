import pytest
from agent_memory.core import distill, sessions
from agent_memory.core.errors import ValidationError
from agent_memory.core.watermark import Watermark


@pytest.mark.parametrize(
    "reply", ["not a JSON operation", '{"look": "recall", "query": "synthetic fixture"}']
)
def test_incomplete_executor_output_does_not_advance_distillation(store, reply):
    pointer = store.archive.append_session("incomplete", ["user: Synthetic archived evidence"])
    messages = sessions.resolve(store.layout, pointer)
    store.config.write.max_rounds = 1
    with pytest.raises(ValidationError):
        distill.distill(store, "incomplete", messages, lambda prompt: reply)
    assert Watermark(store.layout, store.clock).read("incomplete").distilled == 0
    assert sessions.resolve(store.layout, pointer)[0].text == "Synthetic archived evidence"
