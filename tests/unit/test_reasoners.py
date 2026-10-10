"""Executors: text out, text back, and silence whenever the outside world misbehaves."""

import io
import json

import pytest
from agent_memory.core.errors import ReasonerUnavailableError
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
    host = FakeHost(HostResult(text="ok", ok=True, seconds=0.1))
    HostReasoner(host=host)("review this")
    assert host.calls[0][1]["tools_enabled"] is False


def test_a_failed_host_is_reported():
    host = FakeHost(
        HostResult(
            text="usage: claude ...",
            ok=False,
            seconds=0.1,
            error="provider failed for sk-or-super-secret",
        )
    )
    with pytest.raises(ReasonerUnavailableError, match="provider failed") as raised:
        HostReasoner(host=host)("review this")
    assert "sk-or-super-secret" not in str(raised.value)


def test_an_empty_host_reply_is_reported():
    host = FakeHost(HostResult(text="", ok=True, seconds=0.1))
    with pytest.raises(ReasonerUnavailableError, match="empty response"):
        HostReasoner(host=host)("review this")


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


def test_an_endpoint_reasoner_without_credentials_is_reported(monkeypatch):
    monkeypatch.delenv("GEMINI_BASE_URL", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("VERTEX_LOCATION", raising=False)
    with pytest.raises(ReasonerUnavailableError, match="Google Cloud project"):
        EndpointReasoner()("review this")


def test_an_endpoint_reply_of_the_wrong_shape_is_not_mistaken_for_an_answer(monkeypatch):
    monkeypatch.setenv("GEMINI_BASE_URL", "https://example.invalid/openapi")
    monkeypatch.setenv("GEMINI_API_KEY", "token")
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout=None: io.BytesIO(b'{"error": "quota"}'),
    )
    with pytest.raises(ReasonerUnavailableError, match="valid message"):
        EndpointReasoner()("review this")


def test_an_endpoint_that_refuses_the_connection_is_reported_without_the_key(monkeypatch):
    monkeypatch.setenv("GEMINI_BASE_URL", "https://example.invalid/openapi")
    monkeypatch.setenv("GEMINI_API_KEY", "token")

    def explode(request, timeout=None):
        raise OSError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", explode)
    with pytest.raises(ReasonerUnavailableError) as raised:
        EndpointReasoner()("review this")
    assert "endpoint request failed" in str(raised.value)
    assert "token" not in str(raised.value)


def test_a_host_reasoner_is_named_by_dialect_and_runs_that_dialect_s_binary():
    from agent_memory.executor.hosts import BINARIES, HOST_CLAUDE_CODE
    from agent_memory.executor.reasoners import HostReasoner

    reasoner = HostReasoner.for_host(HOST_CLAUDE_CODE)
    assert reasoner.host.spec.binary == BINARIES[HOST_CLAUDE_CODE][0]
    assert reasoner.host.spec.binary != HOST_CLAUDE_CODE
    assert reasoner.host.spec.model == BINARIES[HOST_CLAUDE_CODE][1]


def test_muse_host_reasoner_uses_the_launcher_pinned_by_its_boundary_hook(monkeypatch):
    from agent_memory.core.config import MUSE_LAUNCHER_ENV_VAR
    from agent_memory.executor.hosts import HOST_MUSE_CODE

    launcher = "/managed/bin/mem-muse"
    monkeypatch.setenv(MUSE_LAUNCHER_ENV_VAR, launcher)

    reasoner = HostReasoner.for_host(HOST_MUSE_CODE)

    assert reasoner.host.spec.binary == launcher


def test_a_host_reasoner_marks_its_session_as_the_executor_so_hooks_stand_down():
    from agent_memory.core.config import EXECUTOR_ENV_VAR

    host = FakeHost(HostResult(text="ok", ok=True, seconds=0.1))
    HostReasoner(host=host)("review this")
    assert host.calls[0][1]["environment"][EXECUTOR_ENV_VAR]


def test_the_default_executor_reasons_through_the_host_cli():
    from agent_memory.core.config import ExecutorConfig
    from agent_memory.executor import distiller

    assert isinstance(distiller.distiller(ExecutorConfig()), HostReasoner)
    chosen = distiller.distiller(ExecutorConfig(host="codex"))
    assert chosen.host.spec.name == "codex"


def test_an_executor_configured_for_an_endpoint_uses_it():
    from agent_memory.core.config import ExecutorConfig
    from agent_memory.executor import distiller

    configured = ExecutorConfig(reasoner="endpoint", project="user-project")
    assert isinstance(distiller.distiller(configured), EndpointReasoner)


def test_an_explicit_openai_endpoint_does_not_require_a_google_cloud_project(monkeypatch):
    from agent_memory.core.config import ExecutorConfig
    from agent_memory.executor import distiller

    monkeypatch.setenv("GEMINI_API_KEY", "user-key")
    chosen = distiller.distiller(
        ExecutorConfig(reasoner="endpoint", endpoint="https://models.example/v1")
    )
    assert isinstance(chosen, EndpointReasoner)
    assert chosen.base_url == "https://models.example/v1"


def test_an_explicit_vertex_project_does_not_borrow_an_unrelated_api_key(monkeypatch):
    from agent_memory.executor.credentials import VertexCredentials

    class UserVertex(VertexCredentials):
        def _mint(self):
            return "user-vertex-token"

    monkeypatch.setenv("GEMINI_API_KEY", "unrelated-api-key")
    monkeypatch.delenv("GEMINI_BASE_URL", raising=False)
    sent = {}

    def fake_urlopen(request, timeout=None):
        sent["url"] = request.full_url
        sent["authorization"] = request.headers["Authorization"]
        return io.BytesIO(_reply("verdict line"))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    reasoner = EndpointReasoner(
        credentials=UserVertex(project="user-project", location="global")
    )

    assert reasoner("review this") == "verdict line"
    assert "/projects/user-project/" in sent["url"]
    assert sent["authorization"] == "Bearer user-vertex-token"


def test_the_claude_host_falls_back_to_the_desktop_bundled_binary(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda binary: None)
    monkeypatch.setenv("CLAUDE_CODE_EXECPATH", "/opt/claude-desktop/claude")
    assert HostReasoner.for_host("claude-code").host.spec.binary == "/opt/claude-desktop/claude"
