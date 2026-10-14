"""The library-side distiller: the store's config names who reasons, the host CLI by default.

One extraction for every host (ADR-002 as amended). What is sent and what the reply may do
are decided in the core; this module only picks the pipe the text travels through.
"""

from __future__ import annotations

from agent_memory.core.config import (
    REASONER_ENDPOINT,
    REASONER_HOST,
    REASONER_SESSION_APP_SERVER,
    REASONER_SESSION_STATEFUL,
    REASONER_SESSION_STATELESS,
    ExecutorConfig,
)
from agent_memory.core.errors import ReasonerUnavailableError

from .credentials import VertexCredentials
from .hosts import HOST_CODEX
from .reasoners import (
    AppServerHostReasoner,
    EndpointReasoner,
    HostReasoner,
    StatefulHostReasoner,
)


def distiller(
    config: ExecutorConfig,
) -> EndpointReasoner | HostReasoner | StatefulHostReasoner | AppServerHostReasoner:
    modes = (
        REASONER_SESSION_STATELESS,
        REASONER_SESSION_STATEFUL,
        REASONER_SESSION_APP_SERVER,
    )
    if config.session_mode not in modes:
        raise ReasonerUnavailableError(
            f"unsupported reasoner session mode {config.session_mode!r}"
        )
    if config.session_mode in (REASONER_SESSION_STATEFUL, REASONER_SESSION_APP_SERVER):
        if config.reasoner != REASONER_HOST:
            raise ReasonerUnavailableError(
                f"{config.session_mode} sessions require a host reasoner"
            )
        if config.host != HOST_CODEX:
            raise ReasonerUnavailableError(
                f"{config.session_mode} sessions are unsupported for host {config.host!r}"
            )
        if config.session_mode == REASONER_SESSION_APP_SERVER:
            return AppServerHostReasoner.for_host(config.host, model=config.host_model)
        return StatefulHostReasoner.for_host(config.host, model=config.host_model)
    if config.reasoner == REASONER_HOST:
        return HostReasoner.for_host(config.host, model=config.host_model)
    if config.reasoner == REASONER_ENDPOINT:
        return EndpointReasoner(
            model=config.model,
            timeout_seconds=config.timeout_seconds,
            credentials=VertexCredentials(project=config.project, location=config.location),
            base_url=config.endpoint,
        )
    raise ReasonerUnavailableError(f"unsupported reasoner {config.reasoner!r}")
