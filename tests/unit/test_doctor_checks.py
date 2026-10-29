"""doctor must judge the store as it really is, not as the upstream installer left it."""

import json
import pathlib

from agent_memory.adapters import doctor


def _write(path: pathlib.Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_a_server_beside_the_settings_is_found(tmp_path):
    settings = tmp_path / "settings.json"
    _write(settings, {"hooks": {}})
    _write(
        tmp_path / "mcp.json",
        {"mcpServers": {"agent-memory": {"command": "/opt/mem-mcp"}}},
    )
    servers = doctor._mcp_servers(settings, "mcpServers")
    assert servers is not None
    assert "agent-memory" in servers


def test_the_home_file_is_still_found(tmp_path):
    settings = tmp_path / "home" / "settings.json"
    _write(settings, {"hooks": {}})
    _write(
        tmp_path / ".claude.json",
        {"mcpServers": {"agent-memory": {"command": "/opt/mem-mcp"}}},
    )
    servers = doctor._mcp_servers(settings, "mcpServers")
    assert servers is not None
    assert "agent-memory" in servers


def test_no_configuration_anywhere_is_not_a_crash(tmp_path):
    settings = tmp_path / "home" / "settings.json"
    _write(settings, {"hooks": {}})
    assert doctor._mcp_servers(settings, "mcpServers") is None


def test_a_non_ascii_path_still_matches():
    """A path that is not plain ASCII must survive the comparison.

    The server entry is compared as text, so it has to be rendered the way it
    was written rather than with non-ASCII characters escaped.
    """
    server = {"command": "/Users/工作/ai-agent-memory/repo/.venv/bin/mem-mcp"}
    rendered = json.dumps(server, ensure_ascii=False)
    assert "/Users/工作/ai-agent-memory/repo/.venv/bin/mem-mcp" in rendered


def test_the_probe_token_is_read_through_stray_characters():
    assert doctor._probe_matched("AGENT_MEMORY_READY")
    assert doctor._probe_matched("AGENT_M#EMORY_READY")
    assert doctor._probe_matched("AGENT_M\nEMORY_READY")
    assert not doctor._probe_matched("SORRY")


def test_a_host_binary_is_only_required_when_a_channel_would_run_it(store):
    store.config.executor.reasoner = "endpoint"
    assert not doctor._host_binary_needed(store)
    store.config.executor.reasoner = "host"
    assert doctor._host_binary_needed(store)
