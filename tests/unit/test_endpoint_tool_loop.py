"""The endpoint reasoner as a standard tool-use loop: the model calls tools until it stops."""

import io
import json

import pytest
from agent_memory.core import agentic, prompts, reconcile, sessions, toolkit
from agent_memory.core.errors import ReasonerUnavailableError
from agent_memory.executor.reasoners import EndpointReasoner, EndpointTextReasoner

SKIP = {toolkit.ARG_OPERATIONS: [{"type": "fact", "op": "skip"}]}
BRIEF = prompts.Brief(instructions="instructions", material="material")


class RecordingTrace:
    def __init__(self):
        self.events: list[tuple[str, tuple[object, ...]]] = []

    def batch(self, *fields):
        self.events.append(("batch", fields))

    def round(self, *fields):
        self.events.append(("round", fields))

    def tool_call(self, *fields):
        self.events.append(("tool_call", fields))

    def operations(self, *fields):
        self.events.append(("operations", fields))

    def repair(self, *fields):
        self.events.append(("repair", fields))

    def usage(self, *fields):
        self.events.append(("usage", fields))

    def error(self, *fields):
        self.events.append(("error", fields))

    def run_started(self, *fields):
        self.events.append(("run_started", fields))

    def run_finished(self, *fields):
        self.events.append(("run_finished", fields))


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


def test_the_endpoint_reasoner_exposes_the_last_response_usage_for_the_trace(monkeypatch, store):
    kit = _kit(store)
    usage = {"input_tokens": 10, "cached_input_tokens": 4, "output_tokens": 5}

    def turn_with_usage(*calls, content=None):
        payload = json.loads(_turn(*calls, content=content))
        payload["usage"] = usage
        return json.dumps(payload).encode("utf-8")

    _endpoint(monkeypatch, turn_with_usage((toolkit.TOOL_SUBMIT, SKIP)), _turn(content="done"))
    reasoner = EndpointReasoner(model="a-model")

    reasoner.converse("i", "m", kit)

    assert reasoner.last_usage == usage


def test_a_call_without_usage_leaves_the_trace_usage_absent(monkeypatch):
    _endpoint(monkeypatch, _turn(content="done"))
    reasoner = EndpointReasoner(model="a-model")

    reasoner("the prompt")

    assert reasoner.last_usage is None


def test_the_text_view_delegates_the_usage_of_its_inner_reasoner(monkeypatch):
    usage = {"input_tokens": 7, "output_tokens": 3}

    def turn_with_usage():
        payload = json.loads(_turn(content="done"))
        payload["usage"] = usage
        return json.dumps(payload).encode("utf-8")

    _endpoint(monkeypatch, turn_with_usage())
    view = EndpointTextReasoner(EndpointReasoner(model="a-model"))

    view("the prompt")

    assert view.last_usage == usage


def test_the_endpoint_loop_reports_its_calls_through_negotiate(store, monkeypatch):
    kit = _kit(store)

    _endpoint(
        monkeypatch,
        _turn((toolkit.TOOL_RECALL, {toolkit.ARG_QUERY: "queue timeout"})),
        _turn((toolkit.TOOL_SUBMIT, SKIP)),
        _turn(content="done"),
    )
    trace = RecordingTrace()

    agentic.negotiate(
        store, kit.sheet, BRIEF, EndpointReasoner(model="a-model"), store.config.write, trace=trace
    )

    assert [name for name, _ in trace.events] == ["tool_call", "tool_call"]
    assert trace.events[0][1][0] == toolkit.TOOL_RECALL
    assert trace.events[0][1][1] == {toolkit.ARG_QUERY: "queue timeout"}
    assert trace.events[1][1][0] == toolkit.TOOL_SUBMIT


def test_a_turn_of_the_wrong_shape_is_reported(monkeypatch, store):
    kit = _kit(store)
    _endpoint(monkeypatch, json.dumps({"unexpected": True}).encode("utf-8"))
    with pytest.raises(ReasonerUnavailableError):
        EndpointReasoner(model="a-model").converse("i", "m", kit)
