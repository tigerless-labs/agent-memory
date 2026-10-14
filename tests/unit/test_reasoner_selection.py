import dataclasses

import pytest
from agent_memory.core.config import Config, OperationExecutorConfig
from agent_memory.core.errors import ReasonerUnavailableError
from agent_memory.executor import distiller, selection
from agent_memory.executor.reasoners import (
    AppServerHostReasoner,
    EndpointReasoner,
    HostReasoner,
    StatefulHostReasoner,
)


def test_default_write_uses_the_source_host_while_manage_uses_the_legacy_executor():
    executor = Config.default().executor

    write = selection.resolve(executor, selection.WRITE, source_host="muse-code")
    manage = selection.resolve(executor, selection.MANAGE, source_host="muse-code")

    assert write.reasoner == "host"
    assert write.host == "muse-code"
    assert manage.reasoner == "host"
    assert manage.host == "claude-code"


def test_operation_policies_select_independent_hosts_without_source_override():
    executor = Config.default().executor
    executor.write = OperationExecutorConfig(reasoner="host", host="muse-code")
    executor.manage = OperationExecutorConfig(reasoner="host", host="codex")

    write = selection.resolve(executor, selection.WRITE, source_host="codex")
    manage = selection.resolve(executor, selection.MANAGE, source_host="muse-code")

    assert write.host == "muse-code"
    assert manage.host == "codex"


def test_write_session_mode_is_independent_from_manage():
    executor = Config.default().executor
    executor.write = OperationExecutorConfig(
        reasoner="host", host="codex", session_mode="stateful"
    )

    write = selection.resolve(executor, selection.WRITE, source_host="muse-code")
    manage = selection.resolve(executor, selection.MANAGE)

    assert write.session_mode == "stateful"
    assert manage.session_mode == "stateless"


def test_source_is_an_explicit_write_host_policy_but_is_invalid_for_manage():
    executor = Config.default().executor
    executor.write = OperationExecutorConfig(reasoner="host", host="source")
    executor.manage = OperationExecutorConfig(reasoner="host", host="source")

    assert selection.resolve(executor, selection.WRITE, source_host="codex").host == "codex"
    with pytest.raises(ReasonerUnavailableError, match="manage reasoner host cannot be source"):
        selection.resolve(executor, selection.MANAGE, source_host="muse-code")


def test_operation_endpoint_fields_fall_back_to_legacy_endpoint_fields_individually():
    executor = Config.default().executor
    executor.reasoner = "endpoint"
    executor.endpoint = "https://legacy.example/v1"
    executor.project = "legacy-project"
    executor.manage = OperationExecutorConfig(
        reasoner="endpoint", endpoint="https://manage.example/v1", model="manage-model"
    )

    write = selection.resolve(executor, selection.WRITE, source_host="codex")
    manage = selection.resolve(executor, selection.MANAGE)

    assert write.reasoner == "endpoint"
    assert write.endpoint == "https://legacy.example/v1"
    assert manage.endpoint == "https://manage.example/v1"
    assert manage.model == "manage-model"
    assert manage.project == "legacy-project"


def test_explicit_cli_fields_override_only_the_selected_operation_policy():
    executor = Config.default().executor
    executor.write = OperationExecutorConfig(
        reasoner="endpoint", endpoint="https://write.example/v1", model="write-model"
    )

    chosen = selection.resolve(
        executor,
        selection.WRITE,
        source_host="muse-code",
        reasoner="host",
        host="codex",
        model="cli-model",
    )

    assert chosen.reasoner == "host"
    assert chosen.host == "codex"
    assert chosen.host_model == "cli-model"


def test_unknown_reasoner_fails_closed_instead_of_becoming_a_host():
    configured = dataclasses.replace(Config.default().executor, reasoner="surprise")

    with pytest.raises(ReasonerUnavailableError, match="unsupported reasoner"):
        distiller.distiller(configured)


def test_resolved_host_and_endpoint_policies_build_only_the_selected_transport():
    executor = Config.default().executor
    executor.write = OperationExecutorConfig(reasoner="host", host="muse-code")
    executor.manage = OperationExecutorConfig(
        reasoner="endpoint", endpoint="https://manage.example/v1"
    )

    write = distiller.distiller(selection.resolve(executor, selection.WRITE, source_host="codex"))
    manage = distiller.distiller(selection.resolve(executor, selection.MANAGE))

    assert isinstance(write, HostReasoner)
    assert write.host.spec.name == "muse-code"
    assert isinstance(manage, EndpointReasoner)
    assert manage.base_url == "https://manage.example/v1"


def test_stateful_mode_builds_only_the_supported_codex_transport():
    executor = Config.default().executor
    executor.write = OperationExecutorConfig(
        reasoner="host", host="codex", session_mode="stateful"
    )
    chosen = distiller.distiller(selection.resolve(executor, selection.WRITE))
    assert isinstance(chosen, StatefulHostReasoner)


def test_app_server_mode_builds_only_the_supported_codex_transport():
    executor = Config.default().executor
    executor.write = OperationExecutorConfig(
        reasoner="host", host="codex", session_mode="app-server"
    )
    chosen = distiller.distiller(selection.resolve(executor, selection.WRITE))
    assert isinstance(chosen, AppServerHostReasoner)


@pytest.mark.parametrize(
    ("reasoner", "host", "message"),
    [
        ("host", "muse-code", "unsupported for host"),
        ("host", "claude-code", "unsupported for host"),
        ("endpoint", "", "require a host reasoner"),
    ],
)
def test_stateful_mode_fails_closed_for_unsupported_transports(reasoner, host, message):
    configured = dataclasses.replace(
        Config.default().executor,
        reasoner=reasoner,
        host=host,
        session_mode="stateful",
        endpoint="https://example.invalid/v1",
    )
    with pytest.raises(ReasonerUnavailableError, match=message):
        distiller.distiller(configured)


@pytest.mark.parametrize(
    ("reasoner", "host", "message"),
    [
        ("host", "muse-code", "unsupported for host"),
        ("host", "claude-code", "unsupported for host"),
        ("endpoint", "", "require a host reasoner"),
    ],
)
def test_app_server_mode_fails_closed_for_unsupported_transports(reasoner, host, message):
    configured = dataclasses.replace(
        Config.default().executor,
        reasoner=reasoner,
        host=host,
        session_mode="app-server",
        endpoint="https://example.invalid/v1",
    )
    with pytest.raises(ReasonerUnavailableError, match=message):
        distiller.distiller(configured)


def test_unknown_session_mode_fails_closed():
    configured = dataclasses.replace(Config.default().executor, session_mode="automatic")
    with pytest.raises(ReasonerUnavailableError, match="unsupported reasoner session mode"):
        distiller.distiller(configured)
