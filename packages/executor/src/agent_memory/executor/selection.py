"""Resolve one operation's reasoner policy without changing what the operation does."""

from __future__ import annotations

import dataclasses

from agent_memory.core.config import (
    REASONER_ENDPOINT,
    REASONER_HOST,
    ExecutorConfig,
    OperationExecutorConfig,
)
from agent_memory.core.errors import ReasonerUnavailableError

WRITE = "write"
MANAGE = "manage"
OPERATIONS = (WRITE, MANAGE)
SOURCE = "source"


def resolve(
    config: ExecutorConfig,
    operation: str,
    *,
    source_host: str = "",
    reasoner: str = "",
    host: str = "",
    model: str = "",
) -> ExecutorConfig:
    if operation not in OPERATIONS:
        raise ReasonerUnavailableError(f"unsupported memory operation: {operation}")
    policy: OperationExecutorConfig = getattr(config, operation)
    chosen = dataclasses.replace(
        config,
        reasoner=policy.reasoner or config.reasoner,
        host=policy.host or config.host,
        host_model=policy.host_model or config.host_model,
        model=policy.model or config.model,
        endpoint=policy.endpoint or config.endpoint,
        project=policy.project or config.project,
        location=policy.location or config.location,
        timeout_seconds=policy.timeout_seconds or config.timeout_seconds,
        session_mode=policy.session_mode or config.session_mode,
    )

    selected_host = chosen.host
    if operation == WRITE and source_host and not policy.host:
        selected_host = source_host
    if selected_host == SOURCE:
        if operation != WRITE:
            raise ReasonerUnavailableError("manage reasoner host cannot be source")
        if not source_host:
            raise ReasonerUnavailableError("write reasoner host=source requires --source-host")
        selected_host = source_host
    chosen = dataclasses.replace(chosen, host=selected_host)

    if reasoner:
        chosen = dataclasses.replace(chosen, reasoner=reasoner)
    if host:
        explicit_host = source_host if host == SOURCE and operation == WRITE else host
        if explicit_host == SOURCE or not explicit_host:
            raise ReasonerUnavailableError(f"{operation} reasoner host cannot be source")
        chosen = dataclasses.replace(chosen, host=explicit_host)
    if model:
        if chosen.reasoner == REASONER_ENDPOINT:
            chosen = dataclasses.replace(chosen, model=model)
        else:
            chosen = dataclasses.replace(chosen, host_model=model)
    if chosen.reasoner not in (REASONER_HOST, REASONER_ENDPOINT):
        raise ReasonerUnavailableError(f"unsupported reasoner {chosen.reasoner!r} for {operation}")
    if chosen.reasoner == REASONER_HOST and not chosen.host.strip():
        raise ReasonerUnavailableError(f"{operation} host reasoner requires a host")
    return chosen
