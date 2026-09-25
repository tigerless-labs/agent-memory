"""The library-side distiller: the store's config names who reasons, the host CLI by default.

One extraction for every host (ADR-002 as amended). What is sent and what the reply may do
are decided in the core; this module only picks the pipe the text travels through.
"""

from __future__ import annotations

import os

from agent_memory.core.config import REASONER_ENDPOINT, ExecutorConfig

from .credentials import BASE_URL_ENV, VertexCredentials
from .reasoners import EndpointReasoner, HostReasoner


def distiller(config: ExecutorConfig) -> EndpointReasoner | HostReasoner:
    if config.reasoner != REASONER_ENDPOINT:
        return HostReasoner.for_host(config.host, model=config.host_model)
    if config.endpoint:
        os.environ.setdefault(BASE_URL_ENV, config.endpoint)
    return EndpointReasoner(
        model=config.model,
        timeout_seconds=config.timeout_seconds,
        credentials=VertexCredentials(project=config.project, location=config.location),
    )
