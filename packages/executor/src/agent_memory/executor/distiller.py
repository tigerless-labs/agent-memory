"""The library-side distiller: the store's config names who reasons, the host CLI by default.

One extraction for every host (ADR-002 as amended). What is sent and what the reply may do
are decided in the core; this module only picks the pipe the text travels through.
"""

from __future__ import annotations

from agent_memory.core.config import REASONER_ENDPOINT, ExecutorConfig

from .credentials import VertexCredentials
from .reasoners import EndpointReasoner, HostReasoner


def distiller(config: ExecutorConfig) -> EndpointReasoner | HostReasoner:
    if config.reasoner != REASONER_ENDPOINT:
        return HostReasoner.for_host(config.host, model=config.host_model)
    return EndpointReasoner(
        model=config.model,
        timeout_seconds=config.timeout_seconds,
        credentials=VertexCredentials(project=config.project, location=config.location),
        base_url=config.endpoint,
    )
