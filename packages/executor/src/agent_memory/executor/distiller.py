"""The library-side distiller: the store's config names the model, the endpoint answers.

One extraction for every host (ADR-002 as amended). What is sent and what the reply may do
are decided in the core; this module only carries text across the network.
"""

from __future__ import annotations

import os

from agent_memory.core.config import ExecutorConfig

from .credentials import BASE_URL_ENV
from .reasoners import EndpointReasoner


def distiller(config: ExecutorConfig) -> EndpointReasoner:
    if config.endpoint:
        os.environ.setdefault(BASE_URL_ENV, config.endpoint)
    return EndpointReasoner(model=config.model, timeout_seconds=config.timeout_seconds)
