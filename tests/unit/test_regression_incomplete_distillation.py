import json

import pytest
from agent_memory.core import distill, pending, sessions
from agent_memory.core.errors import ValidationError
from agent_memory.core.watermark import Watermark


@pytest.mark.parametrize(
    "reply",
    [
        "",
        "```json\n```",
        "not a JSON operation",
        '{"look": "recall", "query": "synthetic fixture"}',
    ],
)
def test_incomplete_executor_output_does_not_advance_distillation(store, reply):
    pointer = store.archive.append_session("incomplete", ["user: Synthetic archived evidence"])
    messages = sessions.resolve(store.layout, pointer)
    store.config.write.max_rounds = 1
    with pytest.raises(ValidationError):
        distill.distill(store, "incomplete", messages, lambda prompt: reply)
    assert Watermark(store.layout, store.clock).read("incomplete").distilled == 0
    assert sessions.resolve(store.layout, pointer)[0].text == "Synthetic archived evidence"


def test_mixed_valid_and_malformed_output_does_not_partially_write(store):
    pointer = store.archive.append_session("mixed", ["user: Synthetic archived evidence"])
    messages = sessions.resolve(store.layout, pointer)
    operation = json.dumps(
        {
            "type": "fact",
            "fields": {"subject": "synthetic evidence"},
            "abstract": "Synthetic memory",
            "body": "This must not be written from a partial response.",
            "provenance": ["0"],
        }
    )

    with pytest.raises(ValidationError):
        distill.distill(store, "mixed", messages, lambda prompt: operation + "\nmalformed")

    assert store.records() == []
    assert Watermark(store.layout, store.clock).read("mixed").distilled == 0


def test_incomplete_output_does_not_drain_existing_pending_operations(store):
    pointer = store.archive.append_session("pending", ["user: Synthetic archived evidence"])
    messages = sessions.resolve(store.layout, pointer)
    queued = {"type": "fact", "op": "skip"}
    queue = pending.Pending(store.layout)
    queue.append("pending", [queued])

    with pytest.raises(ValidationError):
        distill.distill(store, "pending", messages, lambda prompt: "")

    assert queue.drain("pending") == [queued]
    assert Watermark(store.layout, store.clock).read("pending").distilled == 0


def test_explicit_skip_is_a_complete_output_and_advances_distillation(store):
    pointer = store.archive.append_session("skip", ["user: Nothing durable to remember"])
    messages = sessions.resolve(store.layout, pointer)
    reply = json.dumps({"type": "fact", "op": "skip"})

    report = distill.distill(store, "skip", messages, lambda prompt: reply)

    assert report.batches[0].written == ()
    assert Watermark(store.layout, store.clock).read("skip").distilled == 1


def test_incomplete_stateful_output_does_not_advance_distillation(store):
    class Run:
        closed = False

        def step(self, _prompt):
            return ""

        def close(self):
            self.closed = True

    class Reasoner:
        def __init__(self):
            self.run = Run()

        def begin(self, _opening):
            return self.run

    pointer = store.archive.append_session("stateful-incomplete", ["user: Evidence"])
    messages = sessions.resolve(store.layout, pointer)
    store.config.write.max_rounds = 1
    reasoner = Reasoner()

    with pytest.raises(ValidationError):
        distill.distill(store, "stateful-incomplete", messages, reasoner)

    assert reasoner.run.closed
    assert Watermark(store.layout, store.clock).read("stateful-incomplete").distilled == 0
