"""Detached launcher for the worker that drains due Write jobs."""

from __future__ import annotations

import os
import subprocess

from agent_memory.core.config import EXECUTOR_ENV_VAR, STORE_ENV_VAR
from agent_memory.core.store import Store
from agent_memory.core.write_jobs import WriteJobs

from . import detached

LOG_FILENAME = "hooks.log"
EXECUTABLE = "mem"
DISTILL_COMMAND = "distill"


def launch(store: Store) -> bool:
    """One detached `mem distill --drain` worker; the queue decides what it runs.

    An OSError here propagates: the hook that offered this opportunity reports it through
    its own fail-safe logging and still exits zero."""
    if WriteJobs(store).due_count() == 0:
        return False
    command = [detached.installed(EXECUTABLE), DISTILL_COMMAND, "--drain"]
    environment = {**os.environ, STORE_ENV_VAR: str(store.root), EXECUTOR_ENV_VAR: "1"}
    store.layout.state_dir.mkdir(parents=True, exist_ok=True)
    with (store.layout.state_dir / LOG_FILENAME).open("a", encoding="utf-8") as log:
        subprocess.Popen(
            command,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            **detached.options(),
        )
    return True
