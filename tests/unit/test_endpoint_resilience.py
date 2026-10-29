"""The endpoint reasoner must survive a gateway that drops a request.

An OpenAI-compatible gateway can close a connection or answer with a truncated
body. Repeating the request is safe because nothing has been appended to the
conversation yet, so the endpoint sees exactly the same request twice.
"""

import io
import json
import urllib.error

import pytest
from agent_memory.adapters.doctor import _probe_matched
from agent_memory.core.errors import ReasonerUnavailableError
from agent_memory.executor.reasoners import EndpointReasoner


def _reply(text):
    return json.dumps({"choices": [{"message": {"content": text}}]}).encode("utf-8")


def _gateway(monkeypatch, *responses):
    """Answer with the given bodies; a body that is an exception is raised instead."""
    monkeypatch.setenv("GEMINI_BASE_URL", "https://example.invalid/openai")
    monkeypatch.setenv("GEMINI_API_KEY", "token")
    monkeypatch.setattr("agent_memory.executor.reasoners.time.sleep", lambda _seconds: None)
    queue = list(responses)
    seen = []

    def fake_urlopen(request, timeout=None):
        seen.append(json.loads(request.data.decode("utf-8")))
        item = queue.pop(0) if queue else urllib.error.URLError("closed")
        if isinstance(item, Exception):
            raise item
        return io.BytesIO(item)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    return seen


def test_a_dropped_request_is_retried(monkeypatch):
    seen = _gateway(monkeypatch, urllib.error.URLError("reset"), _reply("AGENT_MEMORY_READY"))
    reasoner = EndpointReasoner(model="a-model", attempts=3)
    assert reasoner("Reply with exactly AGENT_MEMORY_READY.") == "AGENT_MEMORY_READY"
    assert len(seen) == 2


def test_an_empty_answer_is_retried(monkeypatch):
    seen = _gateway(monkeypatch, _reply(""), _reply("ready"))
    reasoner = EndpointReasoner(model="a-model", attempts=3)
    assert reasoner("prompt") == "ready"
    assert len(seen) == 2


def test_a_gateway_that_never_answers_fails_with_a_reasoner_error(monkeypatch):
    _gateway(monkeypatch, urllib.error.URLError("reset"))
    reasoner = EndpointReasoner(model="a-model", attempts=2)
    with pytest.raises(ReasonerUnavailableError):
        reasoner("prompt")


def test_one_attempt_means_no_retry(monkeypatch):
    seen = _gateway(monkeypatch, urllib.error.URLError("reset"), _reply("ready"))
    reasoner = EndpointReasoner(model="a-model", attempts=1)
    with pytest.raises(ReasonerUnavailableError):
        reasoner("prompt")
    assert len(seen) == 1


def test_a_tool_loop_turn_is_retried_without_polluting_the_conversation(monkeypatch):
    body = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call-1",
                            "type": "function",
                            "function": {"name": "submit", "arguments": "{}"},
                        }
                    ],
                }
            }
        ]
    }
    seen = _gateway(
        monkeypatch,
        urllib.error.URLError("reset"),
        json.dumps(body).encode("utf-8"),
        json.dumps({"choices": [{"message": {"role": "assistant", "content": "done"}}]}).encode(
            "utf-8"
        ),
    )
    reasoner = EndpointReasoner(model="a-model", attempts=3)
    reasoner.converse("instructions", "material", _RecordingToolkit())
    # The retried request is byte-identical to the one that failed: the failed
    # turn never reached the conversation.
    assert seen[0] == seen[1]
    assert len(seen[1]["messages"]) == 2


class _RecordingToolkit:
    """The smallest toolkit the loop needs: one tool, one recorded call."""

    class _Spec:
        name = "submit"
        description = "submit"
        schema = {"type": "object"}

    class _Catalogue:
        def __iter__(self):
            return iter([_RecordingToolkit._Spec()])

    def catalogue(self):
        return self._Catalogue()

    def call(self, name, arguments):
        class _Result:
            text = "ok"

        return _Result()


@pytest.mark.parametrize(
    "reply",
    [
        "AGENT_MEMORY_READY",
        "AGENT_M#EMORY_READY",
        "AGENT_M\nEMORY_READY",
        "  AGENT_MEMORY_READY  ",
    ],
)
def test_the_probe_token_survives_a_stray_character(reply):
    assert _probe_matched(reply)


@pytest.mark.parametrize("reply", ["", "sorry", "READY"])
def test_a_probe_without_the_token_is_not_a_match(reply):
    assert not _probe_matched(reply)
