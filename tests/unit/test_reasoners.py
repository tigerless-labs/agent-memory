"""Executors: text out, text back, and silence whenever the outside world misbehaves."""

import dataclasses
import io
import json
import pathlib
import subprocess

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
    host = FakeHost(HostResult(text="usage: claude ...", ok=False, seconds=0.1, error="boom"))
    with pytest.raises(ReasonerUnavailableError, match="host reasoner failed.*boom"):
        HostReasoner(host=host)("review this")


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


def test_an_unknown_host_reasoner_fails_closed_instead_of_using_another_dialect():
    with pytest.raises(ReasonerUnavailableError, match="unsupported host reasoner"):
        HostReasoner.for_host("not-a-host")


def test_codex_jsonl_usage_is_retained_for_native_review_metrics(tmp_path, monkeypatch):
    from agent_memory.executor import hosts

    def run(command, **kwargs):
        pathlib.Path(command[command.index("--output-last-message") + 1]).write_text("done")
        stdout = json.dumps(
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": 120,
                    "cached_input_tokens": 80,
                    "output_tokens": 12,
                },
            }
        )
        return subprocess.CompletedProcess(command, 0, stdout, "")

    monkeypatch.setattr(hosts.subprocess, "run", run)
    host = hosts.Host(hosts.HostSpec(name="codex", binary="codex", attempts=1))
    result = host.run("review", workdir=tmp_path)

    assert result.ok and result.usage is not None
    assert result.usage.turns == 1
    assert result.usage.input_tokens == 120
    assert result.usage.cached_input_tokens == 80
    assert result.usage.output_tokens == 12


def test_claude_structured_result_supplies_the_answer_and_review_usage(monkeypatch):
    from agent_memory.executor import hosts

    reported = {
        "input_tokens": 40,
        "cache_read_input_tokens": 900,
        "cache_creation_input_tokens": 300,
        "output_tokens": 70,
    }
    turns = 4

    def run(command, **kwargs):
        stdout = json.dumps(
            {
                "type": "result",
                "subtype": "success",
                "is_error": False,
                "result": "review submitted",
                "num_turns": turns,
                "usage": reported,
            }
        )
        return subprocess.CompletedProcess(command, 0, stdout, "")

    monkeypatch.setattr(hosts.subprocess, "run", run)
    host = hosts.Host(hosts.HostSpec(name="claude-code", binary="claude", attempts=1))
    server = hosts.ToolServer(name="memory_review", command="python", args=(), tools=("t",))
    result = host.converse("material", system_prompt="review", server=server)

    assert result.ok and result.usage is not None
    assert result.text == "review submitted"
    assert result.usage.turns == turns
    assert result.usage.input_tokens == (
        reported["input_tokens"]
        + reported["cache_read_input_tokens"]
        + reported["cache_creation_input_tokens"]
    )
    assert result.usage.cached_input_tokens == reported["cache_read_input_tokens"]
    assert result.usage.output_tokens == reported["output_tokens"]


def test_claude_plain_output_keeps_its_text_and_reports_no_usage(monkeypatch):
    from agent_memory.executor import hosts

    def run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, "  a plain answer  ", "")

    monkeypatch.setattr(hosts.subprocess, "run", run)
    host = hosts.Host(hosts.HostSpec(name="claude-code", binary="claude", attempts=1))
    result = host.run("question")

    assert result.ok
    assert result.text == "a plain answer"
    assert result.usage is None


def test_codex_jsonl_trace_separates_startup_model_mcp_and_shutdown():
    from agent_memory.executor.hosts import _CodexTrace

    trace = _CodexTrace(started=10.0)
    trace.observe(json.dumps({"type": "thread.started"}), 11.0)
    trace.observe(
        json.dumps(
            {
                "type": "item.started",
                "item": {"id": "call-1", "type": "mcp_tool_call"},
            }
        ),
        14.0,
    )
    trace.observe(
        json.dumps(
            {
                "type": "item.completed",
                "item": {"id": "call-1", "type": "mcp_tool_call"},
            }
        ),
        14.5,
    )
    trace.observe(json.dumps({"type": "turn.completed"}), 19.0)

    phases = trace.phases(finished=20.0)

    assert phases is not None
    assert phases.startup_seconds == 1.0
    assert phases.model_wait_seconds == 7.5
    assert phases.mcp_seconds == 0.5
    assert phases.shutdown_seconds == 1.0
    assert sum(dataclasses.astuple(phases)) == 10.0


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


def test_hosts_with_a_default_mcp_posture_negotiate_with_tools_and_the_rest_keep_text():
    from agent_memory.core.config import ExecutorConfig
    from agent_memory.core.reasoning import ToolReasoner
    from agent_memory.executor import distiller
    from agent_memory.executor.hosts import BINARIES, DIALECTS

    for name in BINARIES:
        chosen = distiller.distiller(ExecutorConfig(host=name))
        assert isinstance(chosen, ToolReasoner) == DIALECTS[name].tools_by_default, name
        assert callable(chosen)
    assert isinstance(distiller.distiller(ExecutorConfig(reasoner="endpoint")), ToolReasoner)


@pytest.mark.parametrize("name", ["hermes", "muse-code"])
def test_additional_native_write_tools_are_automatic_and_text_can_be_forced(name):
    from agent_memory.core.config import TOOL_MODE_TEXT, ExecutorConfig
    from agent_memory.core.reasoning import ToolReasoner
    from agent_memory.executor import distiller

    native = distiller.distiller(ExecutorConfig(host=name))
    text = distiller.distiller(ExecutorConfig(host=name, tool_mode=TOOL_MODE_TEXT))

    assert isinstance(native, ToolReasoner)
    assert not isinstance(text, ToolReasoner)


def test_native_write_tools_fail_closed_for_an_unknown_host():
    from agent_memory.core.config import TOOL_MODE_NATIVE, ExecutorConfig
    from agent_memory.core.errors import ReasonerUnavailableError
    from agent_memory.executor import distiller

    with pytest.raises(ReasonerUnavailableError, match="does not support native Write tools"):
        distiller.distiller(ExecutorConfig(host="unknown", tool_mode=TOOL_MODE_NATIVE))


def test_hermes_openrouter_does_not_construct_vertex_credentials():
    from agent_memory.core.config import ExecutorConfig
    from agent_memory.executor import distiller
    from agent_memory.executor.hosts import HERMES_DATA_TRAINING_REQUIREMENT

    with pytest.raises(ReasonerUnavailableError, match=HERMES_DATA_TRAINING_REQUIREMENT):
        distiller.distiller(
            ExecutorConfig(
                host="hermes",
                host_provider="openrouter",
                host_model="meta/muse-spark-1.3-contributor",
            )
        )

    chosen = distiller.distiller(
        ExecutorConfig(
            host="hermes",
            host_provider="openrouter",
            host_model="meta/muse-spark-1.3-contributor",
            host_allow_data_training=True,
        )
    )
    assert chosen.host.spec.provider == "openrouter"
    assert chosen.host.spec.allow_data_training is True
    assert chosen.host.credentials is None


def test_an_unknown_write_tool_mode_is_not_silently_downgraded():
    from agent_memory.core.config import ExecutorConfig
    from agent_memory.core.errors import ReasonerUnavailableError
    from agent_memory.executor import distiller

    with pytest.raises(ReasonerUnavailableError, match="unsupported Write tool mode"):
        distiller.distiller(ExecutorConfig(host="muse-code", tool_mode="guess"))


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
    reasoner = EndpointReasoner(credentials=UserVertex(project="user-project", location="global"))

    assert reasoner("review this") == "verdict line"
    assert "/projects/user-project/" in sent["url"]
    assert sent["authorization"] == "Bearer user-vertex-token"


def test_the_claude_host_falls_back_to_the_desktop_bundled_binary(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda binary: None)
    monkeypatch.setenv("CLAUDE_CODE_EXECPATH", "/opt/claude-desktop/claude")
    assert HostReasoner.for_host("claude-code").host.spec.binary == "/opt/claude-desktop/claude"
