"""Executors: text out, text back, and silence whenever the outside world misbehaves."""

import io
import json
import pathlib

import pytest
from agent_memory.core.errors import ReasonerUnavailableError
from agent_memory.executor.hosts import HostResult
from agent_memory.executor.reasoners import (
    AppServerHostReasoner,
    EndpointReasoner,
    HostReasoner,
    StatefulHostReasoner,
)


class FakeHost:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def run(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        return self.result


class FakeSessionHost:
    name = "codex"

    def __init__(self, *results):
        self.results = list(results)
        self.calls = []

    @staticmethod
    def isolated_codex_environment(extra, scratch):
        home = scratch / "codex-home"
        home.mkdir()
        return {**extra, "CODEX_HOME": str(home)}

    def run_session(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        return self.results.pop(0)


class FakeAppServerSession:
    def __init__(self, *results):
        self.results = list(results)
        self.prompts = []
        self.closed = False

    def step(self, prompt):
        self.prompts.append(prompt)
        return self.results.pop(0)

    def close(self):
        self.closed = True


class FakeAppServerHost:
    name = "codex"

    def __init__(self, session):
        self.session = session
        self.opens = 0

    def open_app_server(self):
        self.opens += 1
        return self.session


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
    host = FakeHost(HostResult(text="usage: claude ...", ok=False, seconds=0.1, error="boom"))
    with pytest.raises(ReasonerUnavailableError, match="host reasoner failed.*boom"):
        HostReasoner(host=host)("review this")


def test_an_empty_host_reply_is_reported():
    host = FakeHost(HostResult(text="", ok=True, seconds=0.1))
    with pytest.raises(ReasonerUnavailableError, match="empty response"):
        HostReasoner(host=host)("review this")


def test_a_stateful_host_sends_the_opening_once_and_reuses_the_exact_session():
    host = FakeSessionHost(
        HostResult("look", True, 0.1, session_id="session-a"),
        HostResult("operation", True, 0.1, session_id="session-a"),
    )
    run = StatefulHostReasoner(host=host).begin("opening")
    isolated_home = pathlib.Path(run._environment["CODEX_HOME"])

    assert run.step("") == "look"
    assert run.step("observation delta") == "operation"
    assert host.calls[0][0] == "opening"
    assert host.calls[0][1]["session_id"] == ""
    assert host.calls[1][0] == "observation delta"
    assert host.calls[1][1]["session_id"] == "session-a"
    assert host.calls[0][1]["environment"] == host.calls[1][1]["environment"]
    assert host.calls[0][1]["environment"]["AGENT_MEMORY_EXECUTOR"] == "1"
    assert isolated_home.exists()

    run.close()
    assert not isolated_home.exists()


def test_a_lost_stateful_session_fails_without_starting_over():
    host = FakeSessionHost(
        HostResult("look", True, 0.1, session_id="session-a"),
        HostResult("", False, 0.1, error="session not found", session_id="session-a"),
    )
    run = StatefulHostReasoner(host=host).begin("opening")
    assert run.step("") == "look"

    with pytest.raises(ReasonerUnavailableError, match="session not found"):
        run.step("observation delta")

    assert len(host.calls) == 2
    run.close()


def test_stateful_batches_use_distinct_local_session_homes():
    host = FakeSessionHost()
    reasoner = StatefulHostReasoner(host=host)
    first = reasoner.begin("first")
    second = reasoner.begin("second")

    first_home = pathlib.Path(first._environment["CODEX_HOME"])
    second_home = pathlib.Path(second._environment["CODEX_HOME"])
    assert first_home != second_home
    assert first_home.exists() and second_home.exists()

    first.close()
    second.close()
    assert not first_home.exists() and not second_home.exists()


def test_an_app_server_run_sends_the_opening_once_and_closes_its_process():
    session = FakeAppServerSession(
        HostResult("look", True, 0.1, session_id="session-a"),
        HostResult("operation", True, 0.1, session_id="session-a"),
    )
    host = FakeAppServerHost(session)
    run = AppServerHostReasoner(host=host).begin("opening")

    assert run.step("") == "look"
    assert run.step("observation delta") == "operation"
    assert session.prompts == ["opening", "observation delta"]
    assert host.opens == 1

    run.close()
    run.close()
    assert session.closed


def test_an_app_server_turn_failure_fails_closed_without_another_process():
    session = FakeAppServerSession(
        HostResult("", False, 0.1, error="turn failed", session_id="session-a")
    )
    host = FakeAppServerHost(session)
    run = AppServerHostReasoner(host=host).begin("opening")

    with pytest.raises(ReasonerUnavailableError, match="turn failed"):
        run.step("")

    assert host.opens == 1
    run.close()


def test_app_server_batches_open_and_close_distinct_process_sessions():
    sessions = [FakeAppServerSession(), FakeAppServerSession()]

    class FactoryHost:
        name = "codex"

        def __init__(self):
            self.opens = 0

        def open_app_server(self):
            session = sessions[self.opens]
            self.opens += 1
            return session

    host = FactoryHost()
    reasoner = AppServerHostReasoner(host=host)
    first = reasoner.begin("first")
    second = reasoner.begin("second")

    assert host.opens == 2
    first.close()
    second.close()
    assert all(session.closed for session in sessions)


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


def test_an_unknown_host_reasoner_fails_closed_instead_of_using_another_dialect():
    with pytest.raises(ReasonerUnavailableError, match="unsupported host reasoner"):
        HostReasoner.for_host("not-a-host")


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
