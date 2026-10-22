"""A detached worker outlives the hook that launched it and opens no console window."""

import os
import pathlib
import subprocess
import sys
import textwrap
import time

import pytest
from agent_memory.adapters import detached


@pytest.mark.skipif(os.name == "nt", reason="POSIX launch posture")
def test_posix_workers_start_a_new_session():
    assert detached.options() == {"start_new_session": True}


@pytest.mark.skipif(os.name != "nt", reason="Windows launch posture")
def test_windows_workers_get_their_own_process_group_and_no_console_window():
    flags = detached.options()["creationflags"]
    assert flags & subprocess.CREATE_NEW_PROCESS_GROUP
    assert flags & subprocess.CREATE_NO_WINDOW


def test_a_detached_worker_outlives_its_launcher(tmp_path):
    marker = tmp_path / "worker-finished"
    worker = f"import pathlib, time; time.sleep(1); pathlib.Path({str(marker)!r}).touch()"
    launcher = textwrap.dedent(
        f"""
        import subprocess, sys
        from agent_memory.adapters import detached
        subprocess.Popen(
            [sys.executable, "-c", {worker!r}],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **detached.options(),
        )
        """
    )
    subprocess.run([sys.executable, "-c", launcher], check=True, timeout=30)
    assert not marker.exists()

    deadline = time.monotonic() + 15
    while not marker.exists() and time.monotonic() < deadline:
        time.sleep(0.1)
    assert marker.exists()


def test_installed_entry_points_resolve_without_the_user_path(monkeypatch):
    monkeypatch.setenv("PATH", "")
    resolved = pathlib.Path(detached.installed("mem"))
    assert resolved.is_file()
    assert resolved.parent == pathlib.Path(sys.executable).parent


def test_an_unknown_entry_point_is_left_for_the_caller_to_report():
    assert detached.installed("no-such-agent-memory-binary") == "no-such-agent-memory-binary"
