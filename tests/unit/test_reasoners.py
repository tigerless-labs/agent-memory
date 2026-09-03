"""Executors: text out, text back, and silence whenever the outside world misbehaves."""

import io
import json

from agent_memory.executor.hosts import HostResult
from agent_memory.executor.reasoners import EndpointReasoner, HostReasoner


class FakeHost:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def run(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        return self.result


def _reply(content):
    return json.dumps({"choices": [{"message": {"content": content}}]}).encode("utf-8")


def test_a_host_reasoner_passes_the_prompt_through_and_returns_the_answer():
    host = FakeHost(HostResult(text="verdict line", ok=True, seconds=0.1))
    assert HostReasoner(host=host)("review this") == "verdict line"
    assert host.calls[0][0] == "review this"


def test_a_host_reasoner_asks_for_no_tools():
    host = FakeHost(HostResult(text="", ok=True, seconds=0.1))
    HostReasoner(host=host)("review this")
    assert host.calls[0][1]["tools_enabled"] is False


def test_a_failed_host_says_nothing_rather_than_something_wrong():
    host = FakeHost(HostResult(text="usage: claude ...", ok=False, seconds=0.1, error="boom"))
    assert HostReasoner(host=host)("review this") == ""


def test_an_endpoint_reasoner_reads_the_first_message(monkeypatch):
    monkeypatch.setenv("GEMINI_BASE_URL", "https://example.invalid/openapi")
    monkeypatch.setenv("GEMINI_API_KEY", "token")
    sent = {}

    def fake_urlopen(request, timeout=None):
        sent["url"] = request.full_url
        sent["body"] = json.loads(request.data.decode("utf-8"))
        return io.BytesIO(_reply("verdict line"))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    assert EndpointReasoner()("review this") == "verdict line"
    assert sent["url"].endswith("/chat/completions")
    assert sent["body"]["messages"][0]["content"] == "review this"


def test_an_endpoint_reasoner_without_credentials_stays_silent(monkeypatch):
    monkeypatch.delenv("GEMINI_BASE_URL", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("VERTEX_LOCATION", raising=False)
    assert EndpointReasoner()("review this") == ""


def test_an_endpoint_reply_of_the_wrong_shape_is_not_mistaken_for_an_answer(monkeypatch):
    monkeypatch.setenv("GEMINI_BASE_URL", "https://example.invalid/openapi")
    monkeypatch.setenv("GEMINI_API_KEY", "token")
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout=None: io.BytesIO(b'{"error": "quota"}'),
    )
    assert EndpointReasoner()("review this") == ""


def test_an_endpoint_that_refuses_the_connection_is_survivable(monkeypatch):
    monkeypatch.setenv("GEMINI_BASE_URL", "https://example.invalid/openapi")
    monkeypatch.setenv("GEMINI_API_KEY", "token")

    def explode(request, timeout=None):
        raise OSError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", explode)
    assert EndpointReasoner()("review this") == ""


def test_a_host_reasoner_is_named_by_dialect_and_runs_that_dialect_s_binary():
    from agent_memory.executor.hosts import BINARIES, HOST_CLAUDE_CODE
    from agent_memory.executor.reasoners import HostReasoner

    reasoner = HostReasoner.for_host(HOST_CLAUDE_CODE)
    assert reasoner.host.spec.binary == BINARIES[HOST_CLAUDE_CODE][0]
    assert reasoner.host.spec.binary != HOST_CLAUDE_CODE
    assert reasoner.host.spec.model == BINARIES[HOST_CLAUDE_CODE][1]
