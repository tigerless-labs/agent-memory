"""The library-side distiller: the store's config names who reasons, the host CLI by default.

One extraction for every host (ADR-002 as amended). What is sent and what the reply may do
are decided in the core; this module only picks the pipe the text travels through. A host
whose dialect has an MCP posture runs as a tool-use agent over the Write toolkit; the rest
keep the text protocol.
"""

from __future__ import annotations

from agent_memory.core.config import (
    REASONER_ENDPOINT,
    REASONER_HOST,
    TOOL_MODE_AUTO,
    TOOL_MODE_NATIVE,
    TOOL_MODE_TEXT,
    ExecutorConfig,
)
from agent_memory.core.errors import ReasonerUnavailableError

from .credentials import VertexCredentials
from .hosts import DIALECTS, HERMES_DATA_TRAINING_REQUIREMENT, HOST_HERMES
from .reasoners import EndpointReasoner, HostReasoner, ToolHostReasoner


def distiller(config: ExecutorConfig) -> EndpointReasoner | HostReasoner:
    if config.reasoner == REASONER_HOST:
        dialect = DIALECTS.get(config.host)
        mode = config.tool_mode or TOOL_MODE_AUTO
        if mode not in (TOOL_MODE_AUTO, TOOL_MODE_NATIVE, TOOL_MODE_TEXT):
            raise ReasonerUnavailableError(f"unsupported Write tool mode {mode!r}")
        if mode == TOOL_MODE_NATIVE and (dialect is None or not dialect.supports_tools):
            raise ReasonerUnavailableError(
                f"host reasoner {config.host!r} does not support native Write tools"
            )
        if (
            config.host == HOST_HERMES
            and "contributor" in config.host_model.lower().split("-")
            and not config.host_allow_data_training
        ):
            raise ReasonerUnavailableError(HERMES_DATA_TRAINING_REQUIREMENT)
        speaks_tools = mode == TOOL_MODE_NATIVE or (
            mode == TOOL_MODE_AUTO
            and dialect is not None
            and dialect.supports_tools
            and dialect.tools_by_default
        )
        chosen = ToolHostReasoner if speaks_tools else HostReasoner
        return chosen.for_host(
            config.host,
            model=config.host_model,
            provider=config.host_provider,
            allow_data_training=config.host_allow_data_training,
        )
    if config.reasoner == REASONER_ENDPOINT:
        return EndpointReasoner(
            model=config.model,
            timeout_seconds=config.timeout_seconds,
            credentials=VertexCredentials(project=config.project, location=config.location),
            base_url=config.endpoint,
            attempts=config.attempts,
        )
    raise ReasonerUnavailableError(f"unsupported reasoner {config.reasoner!r}")
