"""The endpoint reasoner as a standard tool-use loop: the model calls tools until it stops."""

import io
import json

import pytest
from agent_memory.core import reconcile, sessions, toolkit
from agent_memory.core.errors import ReasonerUnavailableError
from agent_memory.executor.reasoners import EndpointReasoner

SKIP = {toolkit.ARG_OPERATIONS: [{"type": "fact", "op": "skip"}]}


def _kit(store):
    pointer = store.archive.append_session("boundary", ["user: the queue timeout is 30 seconds"])
    messages = sessions.resolve(store.layout, pointer)
    return toolkit.WriteToolkit(store, reconcile.build(store, "boundary", messages))


def _turn(*calls, content=None):
    message = {"role": "assistant", "content": content}
    if calls:
        message["tool_calls"] = [
            {
                "id": f"call-{index}",
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": arguments if isinstance(arguments, str) else json.dumps(arguments),
                },
            }
            for index, (name, arguments) in enumerate(calls)
        ]
    return json.dumps({"choices": [{"message": message}]}).encode("utf-8")


def _endpoint(monkeypatch, *turns):
    monkeypatch.setenv("GEMINI_BASE_URL", "https://example.invalid/openapi")
    monkeypatch.setenv("GEMINI_API_KEY", "token")
    queue = list(turns)
    bodies = []

    def fake_urlopen(request, timeout=None):
        bodies.append(json.loads(request.data.decode("utf-8")))
        return io.BytesIO(queue.pop(0))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    return bodies


def _answers(body):
    return [message for message in body["messages"] if message["role"] == "tool"]


def test_the_endpoint_runs_tool_calls_until_the_model_stops(monkeypatch, store):
    kit = _kit(store)
    bodies = _endpoint(
        monkeypatch,
        _turn((toolkit.TOOL_RECALL, {toolkit.ARG_QUERY: "queue timeout"})),
        _turn((toolkit.TOOL_SUBMIT, SKIP)),
        _turn(content="done"),
    )
    EndpointReasoner(model="a-model").converse("the instructions", "the material", kit)
    assert kit.submission == SKIP[toolkit.ARG_OPERATIONS]
    assert len(bodies) == 3
    first = bodies[0]
    assert first["messages"] == [
        {"role": "system", "content": "the instructions"},
        {"role": "user", "content": "the material"},
    ]
    assert {tool["function"]["name"] for tool in first["tools"]} == {
        spec.name for spec in kit.catalogue()
    }
    assert all(body["tools"] == first["tools"] for body in bodies)
    assert bodies[-1]["messages"][:2] == first["messages"]
    assert len(_answers(bodies[-1])) == 2


def test_the_endpoint_exposes_and_runs_bounded_evidence_recall(monkeypatch, store):
    store.config.write.recall_with_evidence_enabled = True
    old = store.record(
        name="queue-timeout",
        type="fact",
        fields={"project": "pipeline", "subject": "queue timeout"},
        abstract="Queue timeout is 20 seconds",
        body="Configured in infra/queue.yaml.",
    )
    kit = _kit(store)
    bodies = _endpoint(
        monkeypatch,
        _turn(
            (
                toolkit.TOOL_RECALL_WITH_EVIDENCE,
                {toolkit.ARG_QUERY: "queue timeout"},
            )
        ),
        _turn((toolkit.TOOL_SUBMIT, SKIP)),
        _turn(content="done"),
    )

    EndpointReasoner(model="a-model").converse("i", "m", kit)

    offered = {tool["function"]["name"] for tool in bodies[0]["tools"]}
    assert toolkit.TOOL_RECALL_WITH_EVIDENCE in offered
    assert old.name in _answers(bodies[1])[0]["content"]
    assert "infra/queue.yaml" in _answers(bodies[1])[0]["content"]
    assert old.name in kit.sheet.handle_names()


def test_each_tool_call_is_answered_under_its_own_id_in_order(monkeypatch, store):
    kit = _kit(store)
    bodies = _endpoint(
        monkeypatch,
        _turn(
            (toolkit.TOOL_RECALL, {toolkit.ARG_QUERY: "queue"}),
            (toolkit.TOOL_RECALL, {toolkit.ARG_QUERY: "timeout"}),
            (toolkit.TOOL_SUBMIT, SKIP),
        ),
        _turn(content=""),
    )
    EndpointReasoner(model="a-model").converse("i", "m", kit)
    assert [answer["tool_call_id"] for answer in _answers(bodies[-1])] == [
        "call-0",
        "call-1",
        "call-2",
    ]
    assistant = [m for m in bodies[-1]["messages"] if m["role"] == "assistant"]
    assert len(assistant[0]["tool_calls"]) == 3
    assert kit.submission == SKIP[toolkit.ARG_OPERATIONS]


def test_malformed_tool_arguments_are_answered_and_the_loop_goes_on(monkeypatch, store):
    kit = _kit(store)
    bodies = _endpoint(
        monkeypatch,
        _turn((toolkit.TOOL_SUBMIT, "{not json")),
        _turn((toolkit.TOOL_SUBMIT, SKIP)),
        _turn(content="done"),
    )
    EndpointReasoner(model="a-model").converse("i", "m", kit)
    assert _answers(bodies[1])[0]["content"]
    assert kit.submission == SKIP[toolkit.ARG_OPERATIONS]


def test_the_endpoint_loop_has_no_turn_cap(monkeypatch, store):
    kit = _kit(store)
    looks = [_turn((toolkit.TOOL_RECALL, {toolkit.ARG_QUERY: f"q{n}"})) for n in range(25)]
    bodies = _endpoint(monkeypatch, *looks, _turn((toolkit.TOOL_SUBMIT, SKIP)), _turn())
    EndpointReasoner(model="a-model").converse("i", "m", kit)
    assert len(bodies) == len(looks) + 2
    assert kit.submission == SKIP[toolkit.ARG_OPERATIONS]


def test_a_model_that_stops_without_submitting_leaves_no_submission(monkeypatch, store):
    kit = _kit(store)
    _endpoint(monkeypatch, _turn(content="nothing to add"))
    EndpointReasoner(model="a-model").converse("i", "m", kit)
    assert kit.submission is None


def test_a_turn_of_the_wrong_shape_is_reported(monkeypatch, store):
    kit = _kit(store)
    _endpoint(monkeypatch, json.dumps({"unexpected": True}).encode("utf-8"))
    with pytest.raises(ReasonerUnavailableError):
        EndpointReasoner(model="a-model").converse("i", "m", kit)
