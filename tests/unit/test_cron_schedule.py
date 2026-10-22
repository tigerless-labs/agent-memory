"""User crontab ownership, rendering, and platform diagnostics."""

from __future__ import annotations

import os
import pathlib
import subprocess

import pytest
from agent_memory.adapters import cron_schedule
from agent_memory.core.errors import MemoryStoreError, ValidationError
from agent_memory.core.store import Store

POSIX_CRON = pytest.mark.skipif(os.name == "nt", reason="cron scheduling is POSIX-only")


@pytest.fixture
def cron_harness(tmp_path, monkeypatch):
    state = {"text": "MAILTO=ops@example.test\n7 3 * * * /usr/bin/existing-job\n"}
    binary = tmp_path / "bin" / "mem with spaces"
    binary.parent.mkdir()
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    binary.chmod(0o755)
    monkeypatch.setattr(cron_schedule, "_require_crontab", lambda: "/usr/bin/crontab")
    monkeypatch.setattr(cron_schedule, "_read_crontab", lambda _binary: state["text"])
    monkeypatch.setattr(
        cron_schedule,
        "_write_crontab",
        lambda _binary, content: state.__setitem__("text", content),
    )
    monkeypatch.setattr(cron_schedule, "_scheduler_running", lambda: True)
    monkeypatch.setattr(cron_schedule, "_is_wsl", lambda: False)
    monkeypatch.setenv("HOME", str(tmp_path / "Home With Spaces"))
    monkeypatch.setenv("PATH", f"{tmp_path / 'Tools With Spaces'}:/usr/bin")
    return state, binary


def test_install_is_idempotent_and_quotes_store_executable_environment_and_log(
    tmp_path, cron_harness
):
    state, binary = cron_harness
    store = Store(tmp_path / "Store With Spaces")
    store.init()
    log = tmp_path / "Log With Spaces" / "dream.log"

    first = cron_schedule.install(
        store, interval_minutes=15, mem_path=str(binary), log_path=str(log)
    )
    installed = state["text"]
    second = cron_schedule.install(
        store, interval_minutes=15, mem_path=str(binary), log_path=str(log)
    )

    assert first["status"] == "installed"
    assert first["changed"] is True
    assert first["schedule"] == "*/15 * * * *"
    assert second["status"] == "unchanged"
    assert second["changed"] is False
    assert state["text"] == installed
    assert state["text"].count("# BEGIN agent-memory dream") == 1
    assert "--json sleep --if-due --trigger-source cron" in first["command"]
    assert f"AGENT_MEMORY_STORE='{store.root}'" in first["command"]
    assert f"'{binary}'" in first["command"]
    assert f"'{log}'" in first["command"]
    assert "7 3 * * * /usr/bin/existing-job" in state["text"]


def test_update_status_and_remove_touch_only_the_matching_store(tmp_path, cron_harness):
    state, binary = cron_harness
    first = Store(tmp_path / "first")
    second = Store(tmp_path / "second")
    first.init()
    second.init()
    cron_schedule.install(first, interval_minutes=15, mem_path=str(binary))
    cron_schedule.install(second, interval_minutes=30, mem_path=str(binary))

    updated = cron_schedule.install(first, interval_minutes=60, mem_path=str(binary))
    current = cron_schedule.status(first)
    removed = cron_schedule.remove(first)
    absent = cron_schedule.remove(first)

    assert updated["status"] == "updated"
    assert updated["schedule"] == "0 * * * *"
    assert current["installed"] is True
    assert current["entry"].startswith("0 * * * * ")
    assert removed["status"] == "removed"
    assert removed["installed"] is False
    assert removed["changed"] is True
    assert absent["status"] == "not-installed"
    assert absent["changed"] is False
    assert state["text"].count("# BEGIN agent-memory dream") == 1
    assert cron_schedule.status(second)["installed"] is True
    assert "7 3 * * * /usr/bin/existing-job" in state["text"]


@pytest.mark.parametrize("interval", [0, 7, 61])
def test_install_rejects_intervals_that_do_not_evenly_divide_an_hour(
    tmp_path, cron_harness, interval
):
    _state, binary = cron_harness
    store = Store(tmp_path / "store")
    store.init()
    with pytest.raises(ValidationError, match="must evenly divide an hour"):
        cron_schedule.install(store, interval_minutes=interval, mem_path=str(binary))


def test_install_rejects_an_uninitialized_store(tmp_path, cron_harness):
    _state, binary = cron_harness
    store = Store(tmp_path / "typo-store")
    with pytest.raises(ValidationError, match="not initialized"):
        cron_schedule.install(store, mem_path=str(binary))


def test_percent_is_escaped_for_crontab_before_shell_quoting(tmp_path, cron_harness):
    _state, binary = cron_harness
    store = Store(tmp_path / "percent%store")
    store.init()
    payload = cron_schedule.install(store, mem_path=str(binary))
    assert r"percent\%store" in payload["command"]


@POSIX_CRON
def test_install_rejects_a_store_path_that_could_inject_a_crontab_line(
    tmp_path, cron_harness
):
    _state, binary = cron_harness
    store = Store(tmp_path / "store\n* * * * * injected")
    store.init()

    with pytest.raises(ValidationError, match="store: must not contain a newline or NUL"):
        cron_schedule.install(store, mem_path=str(binary))


def test_missing_crontab_and_mem_binary_are_explicit(tmp_path, cron_harness, monkeypatch):
    _state, _binary = cron_harness
    store = Store(tmp_path / "store")
    store.init()

    def unavailable():
        raise MemoryStoreError("crontab is not installed on this platform")

    monkeypatch.setattr(cron_schedule, "_require_crontab", unavailable)
    with pytest.raises(MemoryStoreError, match="not installed"):
        cron_schedule.status(store)

    monkeypatch.setattr(cron_schedule, "_require_crontab", lambda: "/usr/bin/crontab")
    with pytest.raises(ValidationError, match="not an executable"):
        cron_schedule.install(store, mem_path=str(tmp_path / "missing"))


def test_wsl_status_warns_when_cron_is_not_running(tmp_path, cron_harness, monkeypatch):
    _state, _binary = cron_harness
    store = Store(tmp_path / "store")
    store.init()
    monkeypatch.setattr(cron_schedule, "_is_wsl", lambda: True)
    monkeypatch.setattr(cron_schedule, "_scheduler_running", lambda: False)
    payload = cron_schedule.status(store)
    assert payload["platform"] == "wsl"
    assert payload["scheduler_running"] is False
    assert "cannot wake Memory" in payload["warning"]


def test_malformed_managed_block_is_not_silently_rewritten():
    begin, end = cron_schedule._markers("abc")
    with pytest.raises(MemoryStoreError, match="missing its end marker"):
        cron_schedule._without_block(f"unrelated\n{begin}\n* * * * * command\n", begin, end)


def test_default_log_is_store_local(tmp_path, cron_harness):
    _state, binary = cron_harness
    store = Store(tmp_path / "store")
    store.init()
    payload = cron_schedule.install(store, mem_path=str(binary))
    assert pathlib.Path(payload["log"]) == store.layout.state_dir / cron_schedule.LOG_FILENAME


@POSIX_CRON
def test_private_env_file_is_sourced_without_exposing_its_contents(tmp_path, cron_harness):
    _state, binary = cron_harness
    store = Store(tmp_path / "store")
    store.init()
    environment = tmp_path / "Reasoner Environment"
    environment.write_text("HTTPS_PROXY=https://secret.example\n", encoding="utf-8")
    environment.chmod(0o600)

    payload = cron_schedule.install(
        store,
        mem_path=str(binary),
        env_file=str(environment),
    )

    assert payload["env_file"] == str(environment)
    assert "/bin/sh -c" in payload["command"]
    assert 'set -a; . "$1"; set +a; exec "$2"' in payload["command"]
    assert f"'{environment}'" in payload["command"]
    assert "secret.example" not in payload["command"]


@POSIX_CRON
def test_env_file_invocation_exports_values_to_the_exact_due_aware_command(
    tmp_path, cron_harness
):
    _state, binary = cron_harness
    binary.write_text(
        '#!/bin/sh\nprintf "%s|%s|%s\\n" "$REASONER_ROUTE" "$AGENT_MEMORY_STORE" "$*"\n',
        encoding="utf-8",
    )
    store = Store(tmp_path / "Store With Spaces")
    store.init()
    environment = tmp_path / "Reasoner Environment"
    environment.write_text("REASONER_ROUTE=proxy-route\n", encoding="utf-8")
    environment.chmod(0o600)
    log = tmp_path / "cron output.log"
    payload = cron_schedule.install(
        store,
        mem_path=str(binary),
        log_path=str(log),
        env_file=str(environment),
    )

    completed = subprocess.run(
        str(payload["command"]),
        shell=True,
        executable="/bin/sh",
        check=False,
    )

    assert completed.returncode == 0
    assert log.read_text("utf-8").strip() == (
        f"proxy-route|{store.root}|--json sleep --if-due --trigger-source cron"
    )


def test_env_file_must_be_private(tmp_path, cron_harness):
    _state, binary = cron_harness
    store = Store(tmp_path / "store")
    store.init()
    environment = tmp_path / "reasoner.env"
    environment.write_text("TOKEN=secret\n", encoding="utf-8")
    environment.chmod(0o644)

    with pytest.raises(ValidationError, match="group or others"):
        cron_schedule.install(store, mem_path=str(binary), env_file=str(environment))
