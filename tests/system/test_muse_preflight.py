"""Live Muse compatibility probe; skipped clearly when the binary is unavailable."""

import pathlib
import runpy
import shutil

import pytest


@pytest.mark.skipif(shutil.which("muse") is None, reason="Muse Code binary is not installed")
def test_live_muse_shell_hook_and_mcp_preflight():
    probe = pathlib.Path(__file__).parents[2] / "tools" / "muse_sandbox_probe.py"
    main = runpy.run_path(str(probe))["main"]

    assert main() == 0
