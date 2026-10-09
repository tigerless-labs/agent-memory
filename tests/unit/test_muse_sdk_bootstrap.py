"""Managed Muse SDK bootstrap stays explicit, isolated, and secret-safe."""

from __future__ import annotations

import json
import signal
import subprocess

import pytest
from agent_memory.adapters import doctor, muse_sdk, openrouter, setup
from agent_memory.core.store import Store


def _ready_runtime(tmp_path, monkeypatch, *, cli="Muse Code 1.4.3", sdk="1.4.3"):
    launcher = tmp_path / "bin" / "mem-muse"
    launcher.parent.mkdir()
    launcher.write_text("#!/bin/sh\n", encoding="utf-8")
    launcher.chmod(0o755)
    monkeypatch.setattr(setup, "probe", lambda _host: cli)
    monkeypatch.setattr(muse_sdk, "_launcher_path", lambda _environment: launcher)
    monkeypatch.setattr(muse_sdk, "_node_version", lambda _environment: "20.20.2")
    monkeypatch.setattr(muse_sdk, "_sdk_version", lambda _environment, _cwd: sdk)
    monkeypatch.setattr(
        muse_sdk,
        "_live_preflight",
        lambda *_args, **_kwargs: doctor.Check(
            "SDK_LIVE_OK", True, "managed launcher completed a live request"
        ),
    )
    return launcher


def _codes(payload):
    return {item["code"]: item for item in payload["checks"]}


def test_bootstrap_returns_a_direct_launch_contract_without_persistent_muse_config(
    tmp_path, monkeypatch
):
    launcher = _ready_runtime(tmp_path, monkeypatch)
    credential = openrouter.Credential(
        "sk-or-v1-never-render-this", "environment:OPENROUTER_API_KEY"
    )
    monkeypatch.setattr(openrouter, "detect_credential", lambda _environment=None: credential)
    home = tmp_path / "home"
    environment = {
        "HOME": str(home),
        "PATH": str(launcher.parent),
        "OPENROUTER_API_KEY": credential.value,
    }

    payload = muse_sdk.run(
        Store(tmp_path / "store"),
        provider=openrouter.PROVIDER,
        environment=environment,
        cwd=tmp_path / "app",
    )

    assert payload["status"] == doctor.READY
    assert payload["mode"] == "sdk-managed"
    assert payload["sdk"] == {
        "museBin": str(launcher.resolve()),
        "args": ["serve"],
        "model": openrouter.DEFAULT_MODEL,
        "credential_source": "environment:OPENROUTER_API_KEY",
        "environment": ["AGENT_MEMORY_STORE", "OPENROUTER_API_KEY"],
    }
    assert "SDK_LIVE_OK" in _codes(payload)
    assert not (home / ".config" / "muse" / "settings.json").exists()
    assert not (home / ".config" / "muse" / "auth.json").exists()
    assert credential.value not in json.dumps(payload)
    assert (tmp_path / "store" / "config.toml").is_file()


@pytest.mark.parametrize(
    ("node", "code"),
    [(None, "NODE_MISSING"), ("18.20.0", "NODE_VERSION_UNSUPPORTED")],
)
def test_bootstrap_fails_before_live_request_when_node_is_not_supported(
    tmp_path, monkeypatch, node, code
):
    _ready_runtime(tmp_path, monkeypatch)
    monkeypatch.setattr(muse_sdk, "_node_version", lambda _environment: node)
    monkeypatch.setattr(
        openrouter,
        "detect_credential",
        lambda _environment=None: openrouter.Credential("secret", "environment:OPENROUTER_API_KEY"),
    )
    live_called = False

    def live(*_args, **_kwargs):
        nonlocal live_called
        live_called = True
        return doctor.Check("SDK_LIVE_OK", True, "unexpected")

    monkeypatch.setattr(muse_sdk, "_live_preflight", live)

    payload = muse_sdk.run(Store(tmp_path / "store"), provider=openrouter.PROVIDER)

    assert payload["status"] == doctor.FAILED
    assert code in _codes(payload)
    assert not live_called


def test_bootstrap_reports_the_exact_sdk_install_when_the_project_dependency_is_missing(
    tmp_path, monkeypatch
):
    _ready_runtime(tmp_path, monkeypatch)
    monkeypatch.setattr(muse_sdk, "_sdk_version", lambda _environment, _cwd: None)
    monkeypatch.setattr(
        openrouter,
        "detect_credential",
        lambda _environment=None: openrouter.Credential("secret", "muse-auth:meta"),
    )

    payload = muse_sdk.run(Store(tmp_path / "store"), provider=openrouter.PROVIDER)

    check = _codes(payload)["SDK_PACKAGE_MISSING"]
    assert payload["status"] == doctor.FAILED
    assert check["detail"] == "run `npm install @muse-code/sdk@1.4.3` in the SDK application"


@pytest.mark.parametrize(
    ("sdk", "code", "ready", "required"),
    [
        ("1.4.4", "SDK_VERSION_SKEW", True, False),
        ("2.0.0", "SDK_VERSION_INCOMPATIBLE", False, True),
    ],
)
def test_bootstrap_classifies_sdk_cli_version_skew(
    tmp_path, monkeypatch, sdk, code, ready, required
):
    _ready_runtime(tmp_path, monkeypatch, sdk=sdk)
    monkeypatch.setattr(
        openrouter,
        "detect_credential",
        lambda _environment=None: openrouter.Credential("secret", "muse-auth:meta"),
    )

    payload = muse_sdk.run(Store(tmp_path / "store"), provider=openrouter.PROVIDER)

    assert (payload["status"] == doctor.READY) is ready
    assert _codes(payload)[code]["required"] is required


def test_bootstrap_reports_missing_credentials_without_rendering_auth_paths(tmp_path, monkeypatch):
    _ready_runtime(tmp_path, monkeypatch)
    monkeypatch.setattr(openrouter, "detect_credential", lambda _environment=None: None)

    payload = muse_sdk.run(Store(tmp_path / "store"), provider=openrouter.PROVIDER)

    check = _codes(payload)["OPENROUTER_CREDENTIAL_MISSING"]
    assert payload["status"] == doctor.FAILED
    assert check["detail"] == (
        "set OPENROUTER_API_KEY in both bootstrap and application environments, "
        "or provision Muse auth"
    )
    assert "auth.json" not in json.dumps(payload)


def test_live_preflight_passes_the_store_and_redacts_child_output(tmp_path, monkeypatch):
    launcher = tmp_path / "mem-muse"
    credential = openrouter.Credential("sk-or-v1-private", "environment:OPENROUTER_API_KEY")
    observed = {}

    class Process:
        pid = 42
        returncode = 1

        def communicate(self, timeout):
            observed["timeout"] = timeout
            return "", f"upstream rejected {credential.value}"

    def execute(command, **kwargs):
        observed.update(command=command, **kwargs)
        return Process()

    monkeypatch.setattr(muse_sdk.subprocess, "Popen", execute)

    check = muse_sdk._live_preflight(
        launcher,
        Store(tmp_path / "store"),
        credential,
        openrouter.DEFAULT_MODEL,
        {"PATH": "/bin", "OPENROUTER_API_KEY": credential.value},
    )

    assert not check.ok
    assert credential.value not in check.detail
    assert observed["env"]["AGENT_MEMORY_STORE"] == str((tmp_path / "store").resolve())
    assert observed["command"][0] == str(launcher)
    assert observed["start_new_session"] is True


def test_live_preflight_terminates_the_complete_process_group_on_timeout(tmp_path, monkeypatch):
    launcher = tmp_path / "mem-muse"
    credential = openrouter.Credential("secret", "environment:OPENROUTER_API_KEY")
    signals = []

    class Process:
        pid = 73
        returncode = -signal.SIGTERM
        calls = 0

        def communicate(self, timeout):
            self.calls += 1
            if self.calls == 1:
                raise subprocess.TimeoutExpired([str(launcher)], timeout)
            return "", ""

    monkeypatch.setattr(muse_sdk.subprocess, "Popen", lambda *_args, **_kwargs: Process())
    monkeypatch.setattr(muse_sdk.os, "killpg", lambda pid, signum: signals.append((pid, signum)))

    check = muse_sdk._live_preflight(
        launcher,
        Store(tmp_path / "store"),
        credential,
        openrouter.DEFAULT_MODEL,
        {},
    )

    assert check.code == "SDK_LIVE_UNAVAILABLE"
    assert "timed out" in check.detail
    assert signals == [(73, signal.SIGTERM)]


def test_no_live_bootstrap_never_claims_readiness(tmp_path, monkeypatch):
    _ready_runtime(tmp_path, monkeypatch)
    monkeypatch.setattr(
        openrouter,
        "detect_credential",
        lambda _environment=None: openrouter.Credential("secret", "muse-auth:meta"),
    )

    payload = muse_sdk.run(
        Store(tmp_path / "store"), provider=openrouter.PROVIDER, live=False
    )

    assert payload["status"] == doctor.FAILED
    assert "SDK_LIVE_PREFLIGHT_SKIPPED" in _codes(payload)
