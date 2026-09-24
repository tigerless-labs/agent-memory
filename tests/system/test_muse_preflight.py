"""Live Muse compatibility probe; skipped clearly when the binary is unavailable."""

import shutil

import pytest


@pytest.mark.skipif(shutil.which("muse") is None, reason="Muse Code binary is not installed")
def test_live_muse_shell_hook_and_mcp_preflight():
    from tools.muse_sandbox_probe import main

    assert main() == 0
