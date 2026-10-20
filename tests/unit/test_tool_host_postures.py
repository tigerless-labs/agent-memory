"""Host CLIs run Write tools-only: the toolkit over MCP, nothing of their own."""

import json
import tomllib

import pytest
from agent_memory.core import toolkit
from agent_memory.executor import hosts

TOOLS = (
    toolkit.TOOL_RECALL,
    toolkit.TOOL_RECALL_WITH_EVIDENCE,
    toolkit.TOOL_READ,
    toolkit.TOOL_SUBMIT,
)
SERVER = hosts.ToolServer(
    name="memory",
    command="/venv/bin/python",
    args=("-m", "agent_memory.mcp.write_session", "/tmp/batch"),
    tools=TOOLS,
)
SYSTEM = "You are filling in a long-term memory store."


def _spec(name):
    return hosts.HostSpec(name=name, binary=name, model="a-model")


def _command(name, tmp_path):
    return hosts.DIALECTS[name].tool_command(
        _spec(name),
        system_prompt=SYSTEM,
        instructions_file=tmp_path / "instructions.md",
        server=SERVER,
        answer_file=tmp_path / "answer.txt",
    )


def _after(command, flag):
    return command[command.index(flag) + 1]


def _overrides(command):
    pairs = [command[i + 1] for i, part in enumerate(command) if part == "-c"]
    return tomllib.loads("\n".join(pairs))


def test_supported_hosts_can_run_write_tools_over_mcp():
    supported = {name for name, dialect in hosts.DIALECTS.items() if dialect.supports_tools}
    assert supported == {
        hosts.HOST_CLAUDE_CODE,
        hosts.HOST_CODEX,
        hosts.HOST_HERMES,
        hosts.HOST_MUSE_CODE,
    }


def test_supported_hosts_use_native_write_tools_by_default():
    defaults = {name for name, dialect in hosts.DIALECTS.items() if dialect.tools_by_default}
    assert defaults == {
        hosts.HOST_CLAUDE_CODE,
        hosts.HOST_CODEX,
        hosts.HOST_HERMES,
        hosts.HOST_MUSE_CODE,
    }


@pytest.mark.parametrize(
    "name",
    [hosts.HOST_CLAUDE_CODE, hosts.HOST_CODEX, hosts.HOST_HERMES, hosts.HOST_MUSE_CODE],
)
def test_tool_commands_keep_native_memory_off(name, tmp_path):
    command = _command(name, tmp_path)
    assert command[0] == name
    assert "a-model" in command
    assert hosts.DIALECTS[name].disables_native_memory(" ".join(command))


def test_claude_code_sees_only_the_toolkit_through_a_strict_mcp_config(tmp_path):
    command = _command(hosts.HOST_CLAUDE_CODE, tmp_path)
    assert "--strict-mcp-config" in command
    configured = json.loads(_after(command, "--mcp-config"))["mcpServers"]
    assert set(configured) == {SERVER.name}
    assert configured[SERVER.name]["command"] == SERVER.command
    assert configured[SERVER.name]["args"] == list(SERVER.args)
    assert _after(command, "--tools") == ""
    allowed = set(_after(command, "--allowedTools").split(","))
    assert allowed == {f"mcp__{SERVER.name}__{tool}" for tool in TOOLS}
    assert _after(command, "--system-prompt") == SYSTEM


def test_claude_code_runs_without_a_turn_cap_and_keeps_its_login(tmp_path):
    command = _command(hosts.HOST_CLAUDE_CODE, tmp_path)
    assert "--max-turns" not in command
    assert "--bare" not in command


def test_codex_replaces_its_instructions_and_requires_the_toolkit_server(tmp_path):
    command = _command(hosts.HOST_CODEX, tmp_path)
    assert command[1] == "exec"
    assert {"--ignore-user-config", "--ignore-rules", "--ephemeral"} <= set(command)
    assert _after(command, "--sandbox") == "read-only"
    overrides = _overrides(command)
    assert overrides["model_instructions_file"] == str(tmp_path / "instructions.md")
    server = overrides["mcp_servers"][SERVER.name]
    assert server["command"] == SERVER.command
    assert server["args"] == list(SERVER.args)
    assert server["required"] is True
    assert set(server["enabled_tools"]) == set(TOOLS)
    assert server["default_tools_approval_mode"] == "approve"


def test_codex_turns_off_local_execution(tmp_path):
    command = _command(hosts.HOST_CODEX, tmp_path)
    disabled = {command[i + 1] for i, part in enumerate(command) if part == "--disable"}
    assert {"shell_tool", "unified_exec", "multi_agent", "plugins", "apps"} <= disabled
    assert "--add-dir" not in command
    assert SYSTEM not in " ".join(command)


def test_hermes_selects_only_the_isolated_write_server(tmp_path):
    command = _command(hosts.HOST_HERMES, tmp_path)

    assert command[1:3] == ["chat", "--oneshot"]
    assert _after(command, "--toolsets") == hosts.HERMES_WRITE_SERVER_NAME
    assert _after(command, "--max-turns") == str(hosts.HERMES_NATIVE_MAX_TURNS)
    assert "--query-file" in command
    assert "--ignore-rules" in command
    assert "--ignore-user-config" not in command
    assert "--safe-mode" not in command
    assert "terminal" not in command
    assert SYSTEM not in " ".join(command)


def test_hermes_openrouter_keeps_the_publisher_qualified_model(tmp_path):
    spec = hosts.HostSpec(
        name=hosts.HOST_HERMES,
        binary="hermes",
        provider="openrouter",
        model="meta/muse-spark-1.3-contributor",
    )
    command = hosts.DIALECTS[hosts.HOST_HERMES].tool_command(
        spec,
        system_prompt=SYSTEM,
        instructions_file=tmp_path / "instructions.md",
        server=SERVER,
        answer_file=tmp_path / "answer.txt",
    )

    assert _after(command, "--provider") == "openrouter"
    assert _after(command, "--model") == "meta/muse-spark-1.3-contributor"


def test_muse_turns_off_unrelated_tools_and_keeps_the_sandbox(tmp_path):
    command = _command(hosts.HOST_MUSE_CODE, tmp_path)

    assert command[1] == "exec"
    assert _after(command, "-c") == (
        'run.toolset=["mcp__memory__recall", "mcp__memory__recall_with_evidence", '
        '"mcp__memory__read", '
        '"mcp__memory__submit_operations"]'
    )
    assert {
        "--no-foreign-personal-context",
        "--disable-reminders",
        "--no-session-log",
        "--disable-shell",
        "--disable-web-tools",
        "--disable-write",
    } <= set(command)
    assert _after(command, "--approval-mode") == "never"
    assert "--disable-sandbox" not in command
    assert "--yolo" not in command
    assert _after(command, "--max-model-steps") == str(hosts.MUSE_NATIVE_MAX_MODEL_STEPS)
    assert SYSTEM not in " ".join(command)
