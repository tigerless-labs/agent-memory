"""Short-lived credentials: minted on demand, refreshed before they go stale, never logged."""

from agent_memory.executor import credentials
from agent_memory.executor.credentials import VertexCredentials


class Minting(VertexCredentials):
    def __init__(self, token="token-one"):
        super().__init__()
        self.calls = 0
        self.next_token = token

    def _mint(self):
        self.calls += 1
        return self.next_token


def _configure(monkeypatch, project="a-project", location="global", preset=None):
    monkeypatch.setenv(credentials.PROJECT_ENV, project)
    monkeypatch.setenv(credentials.LOCATION_ENV, location)
    monkeypatch.delenv(credentials.API_KEY_ENV, raising=False)
    if preset:
        monkeypatch.setenv(credentials.API_KEY_ENV, preset)


def test_the_endpoint_is_built_from_the_project_and_location(monkeypatch):
    _configure(monkeypatch, project="tigerless", location="global")
    environment = Minting().environment()
    assert "tigerless" in environment[credentials.BASE_URL_ENV]
    assert "/locations/global/" in environment[credentials.BASE_URL_ENV]
    assert environment[credentials.API_KEY_ENV] == "token-one"


def test_a_token_is_reused_until_it_is_close_to_stale(monkeypatch):
    _configure(monkeypatch)
    minter = Minting()
    assert minter._token(now=0.0) == "token-one"
    minter.next_token = "token-two"
    assert minter._token(now=credentials.REFRESH_SECONDS / 2) == "token-one"
    assert minter.calls == 1


def test_a_stale_token_is_replaced(monkeypatch):
    _configure(monkeypatch)
    minter = Minting()
    minter._token(now=0.0)
    minter.next_token = "token-two"
    assert minter._token(now=credentials.REFRESH_SECONDS + 1) == "token-two"
    assert minter.calls == 2


def test_an_explicit_key_in_the_environment_is_left_alone(monkeypatch):
    _configure(monkeypatch, preset="a-key-the-operator-set")
    minter = Minting()
    assert minter.environment() == {}
    assert minter.calls == 0


def test_no_project_means_no_credentials_rather_than_a_broken_command(monkeypatch):
    monkeypatch.delenv(credentials.PROJECT_ENV, raising=False)
    monkeypatch.delenv(credentials.LOCATION_ENV, raising=False)
    assert Minting().environment() == {}


def test_a_failed_mint_yields_nothing_instead_of_a_half_configured_host(monkeypatch):
    _configure(monkeypatch)

    class Failing(VertexCredentials):
        def _mint(self):
            return ""

    assert Failing().environment() == {}


def test_only_hermes_carries_credentials(monkeypatch):
    from agent_memory.executor.hosts import (
        HOST_CLAUDE_CODE,
        HOST_CODEX,
        HOST_HERMES,
        Host,
        HostSpec,
    )

    assert Host(HostSpec(name=HOST_HERMES, binary="hermes")).credentials is not None
    for name in (HOST_CLAUDE_CODE, HOST_CODEX):
        assert Host(HostSpec(name=name, binary=name)).credentials is None


def test_the_configured_project_is_used_when_the_environment_says_nothing(monkeypatch):
    monkeypatch.delenv(credentials.PROJECT_ENV, raising=False)
    monkeypatch.delenv(credentials.LOCATION_ENV, raising=False)
    monkeypatch.delenv(credentials.API_KEY_ENV, raising=False)
    minter = Minting()
    minter.project = "built-in"
    minter.location = "global"
    environment = minter.environment()
    assert "/projects/built-in/" in environment[credentials.BASE_URL_ENV]


def test_the_environment_overrides_the_configured_project(monkeypatch):
    _configure(monkeypatch, project="from-env", location="us-central1")
    minter = Minting()
    minter.project = "built-in"
    minter.location = "global"
    environment = minter.environment()
    assert "/projects/from-env/" in environment[credentials.BASE_URL_ENV]
    assert "/locations/us-central1/" in environment[credentials.BASE_URL_ENV]


def test_the_distiller_hands_the_configured_project_to_the_minter():
    from agent_memory.core.config import ExecutorConfig
    from agent_memory.executor.distiller import distiller

    reasoner = distiller(ExecutorConfig(project="built-in", location="global"))
    assert reasoner.credentials.project == "built-in"
    assert reasoner.credentials.location == "global"
