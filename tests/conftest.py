import datetime as dt
import os
import sys

import pytest
from agent_memory.core.clock import FrozenClock
from agent_memory.core.config import Config
from agent_memory.core.store import Store

EPOCH = dt.datetime(2026, 1, 15, 9, 0, tzinfo=dt.UTC)
WINDOWS_SYMLINK_PRIVILEGE_NOT_HELD = 1314


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    try:
        return (yield)
    except OSError as error:
        if getattr(error, "winerror", None) == WINDOWS_SYMLINK_PRIVILEGE_NOT_HELD:
            pytest.skip("creating symlinks needs Developer Mode or administrator rights on Windows")
        raise


@pytest.fixture
def clock() -> FrozenClock:
    return FrozenClock(EPOCH)


@pytest.fixture
def config() -> Config:
    return Config.default()


@pytest.fixture
def store(tmp_path, config, clock) -> Store:
    store = Store(tmp_path / "store", config=config, clock=clock, agent="test-agent")
    store.init()
    return store


@pytest.fixture
def seeded(store):
    store.record(
        abstract="Ryan prefers concise answers with no preamble",
        type="preference",
        body="Answer in the fewest words possible.",
        name="ryan-prefers-concise-answers",
    )
    store.record(
        abstract="The staging deploy fails with error E4021 when the queue is drained",
        type="experience",
        body=(
            "# Symptom\nDeploy aborts at the drain step and the rollout controller reports "
            "error E4021 while the queue still holds unacknowledged jobs.\n\n"
            "# Cause\nThe worker lease outlives the queue drain window, so the drain check "
            "observes a live lease and refuses to declare the queue empty.\n\n"
            "# Fix\nRaise drain_timeout above the lease TTL in infra/queue.yaml, then redeploy "
            "and confirm the drain step completes before the controller times out.\n"
        ),
        name="staging-deploy-e4021",
    )
    store.record(
        abstract="agent-memory keeps markdown files as the single source of truth",
        type="decision",
        body="Indexes are rebuildable caches; rm -rf .index loses zero knowledge.",
        name="file-truth-invariant",
    )
    return store


@pytest.fixture
def python_executable():
    """Python source installed as a command the way each platform runs one.

    POSIX gets a shebang script; Windows gets the script plus a .cmd launcher beside it,
    the same shape as npm-installed host CLIs, so the extensionless path resolves on PATHEXT."""

    def install(path, source):
        path.parent.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            script = path.with_suffix(".py")
            script.write_text(source, encoding="utf-8")
            path.with_suffix(".cmd").write_text(
                f'@"{sys.executable}" "{script}" %*\r\n', encoding="utf-8"
            )
        else:
            path.write_text(source, encoding="utf-8")
            path.chmod(0o755)
        return path

    return install


FAKE_MEMCORE = """#!/usr/bin/env bash
set -eu
log() { if [ -n "${MEMCORE_DIR:-}" ]; then echo "$*" >> "$MEMCORE_DIR/calls.log"; fi; }
case "$1" in
  --version) echo "memcore 0.0-fake" ;;
  init) shift; shift; mkdir -p "$1/memories" ;;
  create) log "create $2"; cat > "$MEMCORE_DIR/memories/$2.md" ;;
  recall) log "recall"; ls "$MEMCORE_DIR/memories" 2>/dev/null | sed 's/\\.md$//' ;;
  get) log "get $2"; cat "$MEMCORE_DIR/memories/$2.md" ;;
  stop) log "stop" ;;
  *) log "$*" ;;
esac
"""
FAKE_MEMCORE_SKILL = (
    "# MemCore skill\nUse memcore recall before acting and memcore create while acting."
)


@pytest.fixture
def memcore_home(tmp_path):
    """A MemCore checkout in release layout, with a shell script standing in for the binary."""
    import stat

    if os.name == "nt":
        pytest.skip("the MemCore comparison system ships a POSIX binary")

    home = tmp_path / "memcli"
    home.mkdir()
    binary = home / "memcore"
    binary.write_text(FAKE_MEMCORE, encoding="utf-8")
    binary.chmod(binary.stat().st_mode | stat.S_IEXEC)
    (home / "SKILL.md").write_text(FAKE_MEMCORE_SKILL, encoding="utf-8")
    (home / "models").mkdir()
    (home / "models" / "config.json").write_text("{}", encoding="utf-8")
    return home
