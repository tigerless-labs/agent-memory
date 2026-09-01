import datetime as dt

import pytest
from agent_memory.core.clock import FrozenClock
from agent_memory.core.config import Config
from agent_memory.core.store import Store

EPOCH = dt.datetime(2026, 1, 15, 9, 0, tzinfo=dt.UTC)


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
        domain="user",
        body="Answer in the fewest words possible.",
        name="ryan-prefers-concise-answers",
    )
    store.record(
        abstract="The staging deploy fails with error E4021 when the queue is drained",
        type="experience",
        domain="experience",
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
        domain="project",
        body="Indexes are rebuildable caches; rm -rf .index loses zero knowledge.",
        name="file-truth-invariant",
    )
    return store
