"""Live Muse compatibility probe; skipped clearly when the binary is unavailable."""

import os
import pathlib
import runpy
import shutil
import stat

import pytest


def test_muse_preflight_uses_canonical_mcp_tool_name():
    probe = pathlib.Path(__file__).parents[2] / "tools" / "muse_sandbox_probe.py"
    namespace = runpy.run_path(str(probe))

    assert "Call the mcp__agent_memory__memory_record MCP tool" in namespace["_mcp_prompt"]()


def test_muse_preflight_stages_only_auth_in_isolated_config(tmp_path):
    probe = pathlib.Path(__file__).parents[2] / "tools" / "muse_sandbox_probe.py"
    stage_auth = runpy.run_path(str(probe))["_stage_auth"]
    source = tmp_path / "source" / "auth.json"
    source.parent.mkdir()
    source.write_text('{"secret":"not-printed"}', encoding="utf-8")
    config_home = tmp_path / "isolated-config"
    config_home.joinpath("muse").mkdir(parents=True)

    staged = stage_auth(source, config_home)

    assert staged == config_home / "muse" / "auth.json"
    assert staged.read_bytes() == source.read_bytes()
    assert os.name == "nt" or stat.S_IMODE(staged.stat().st_mode) == 0o600


@pytest.mark.skipif(
    shutil.which("muse") is None or os.environ.get("AGENT_MEMORY_LIVE_MUSE") != "1",
    reason="set AGENT_MEMORY_LIVE_MUSE=1 with an installed, authenticated Muse Code",
)
def test_live_muse_shell_hook_and_mcp_preflight():
    probe = pathlib.Path(__file__).parents[2] / "tools" / "muse_sandbox_probe.py"
    main = runpy.run_path(str(probe))["main"]

    assert main() == 0
