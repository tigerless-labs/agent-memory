"""Unified setup/doctor contract across Claude Code, Codex and Muse Code."""

from __future__ import annotations

import json
import pathlib
import subprocess

import pytest
from agent_memory.adapters import doctor, host_setup, moments, openrouter, setup
from agent_memory.core import prompts
from agent_memory.core.errors import ValidationError
from agent_memory.core.store import Store

HOSTS = (moments.HOST_CLAUDE_CODE, moments.HOST_CODEX, moments.HOST_MUSE_CODE)


@pytest.fixture(autouse=True)
def _stub_live_host_reasoner(monkeypatch):
    """No host process is launched by setup fixtures, including Claude Code."""
    monkeypatch.setattr(
        doctor,
        "_live_reasoner_check",
        lambda _store, _host: doctor.Check(
            "REASONER_LIVE_OK", True, "fixture host reasoner completed"
        ),
    )


@pytest.mark.parametrize("host", HOSTS)
def test_fresh_and_repeated_setup_share_one_idempotent_pipeline(tmp_path, monkeypatch, host):
    target = tmp_path / host / "settings.json"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps({"theme": "preserve-me"}), encoding="utf-8")
    store = Store(tmp_path / "external-store")
    monkeypatch.setattr(setup, "probe", lambda selected: f"{selected} 1.0")

    first = host_setup.run(store, host, settings_path=target)
    once = target.read_bytes()
    second = host_setup.run(store, host, settings_path=target)

    assert first["status"] == second["status"] == doctor.READY
    assert target.read_bytes() == once
    configured = json.loads(target.read_text(encoding="utf-8"))
    assert configured["theme"] == "preserve-me"
    assert store.root == (tmp_path / "external-store").resolve()
    assert (store.root / "config.toml").is_file()
    assert setup.skill_path(host, target).read_text(encoding="utf-8") == prompts.skill()
    for event in moments.DIALECTS[host]:
        rendered = json.dumps(configured["hooks"][event])
        assert rendered.count(f"mem-hook --host {host}") == 1
        assert str(store.root) in rendered


@pytest.mark.parametrize("host", HOSTS)
def test_probe_classifies_a_missing_host_binary(monkeypatch, host):
    monkeypatch.setattr(setup.shutil, "which", lambda _binary: None)
    with pytest.raises(ValidationError, match="requires"):
        setup.probe(host)


@pytest.mark.parametrize("host", HOSTS)
def test_setup_reports_missing_binary_without_writing_config(tmp_path, monkeypatch, host):
    target = tmp_path / host / "settings.json"
    monkeypatch.setattr(setup.shutil, "which", lambda _binary: None)

    result = host_setup.run(Store(tmp_path / "store"), host, settings_path=target)

    assert result["status"] == doctor.FAILED
    assert result["checks"][0]["code"] == "HOST_BINARY_MISSING"
    assert not target.exists()


@pytest.mark.parametrize("host", HOSTS)
def test_malformed_host_config_is_never_overwritten(tmp_path, host):
    target = tmp_path / host / "settings.json"
    target.parent.mkdir(parents=True)
    original = b'{"hooks": nope'
    target.write_bytes(original)

    with pytest.raises(ValidationError, match="malformed JSON"):
        setup.install(host, target, tmp_path / "store")

    assert target.read_bytes() == original


def test_muse_openrouter_routing_and_mcp_merge_without_replacing_other_config(tmp_path):
    target = tmp_path / "muse" / "settings.json"
    target.parent.mkdir(parents=True)
    target.write_text(
        json.dumps({"theme": "dark", "mcp_servers": {"other": {"command": "other"}}}),
        encoding="utf-8",
    )
    store = tmp_path / "store"

    setup.install(
        moments.HOST_MUSE_CODE,
        target,
        store,
        provider=openrouter.PROVIDER,
        mcp=True,
    )
    once = target.read_bytes()
    setup.install(
        moments.HOST_MUSE_CODE,
        target,
        store,
        provider=openrouter.PROVIDER,
        mcp=True,
    )
    configured = json.loads(target.read_text(encoding="utf-8"))

    assert target.read_bytes() == once
    assert configured["theme"] == "dark"
    assert configured["provider"] == "meta"
    assert configured["model"] == "muse-spark-1.3-contributor"
    assert configured["endpoint_transport"] == {
        "base_url": openrouter.DEFAULT_PROXY_URL,
        "auth": "bearer",
    }
    assert configured["mcp_servers"]["other"] == {"command": "other"}
    assert str(store.resolve()) in json.dumps(configured["mcp_servers"]["agent-memory"])


@pytest.mark.parametrize(
    ("existing", "field"),
    [
        ({"provider": "local"}, "settings.provider"),
        ({"model": "user-model"}, "settings.model"),
        ({"endpoint_transport": {"base_url": "https://user.example"}}, "endpoint_transport"),
    ],
)
def test_muse_provider_conflicts_fail_without_overwrite(tmp_path, existing, field):
    target = tmp_path / "settings.json"
    target.write_text(json.dumps(existing), encoding="utf-8")
    original = target.read_bytes()

    with pytest.raises(ValidationError, match=field):
        setup.install(
            moments.HOST_MUSE_CODE,
            target,
            tmp_path / "store",
            provider=openrouter.PROVIDER,
        )

    assert target.read_bytes() == original


def _provider_target(tmp_path: pathlib.Path) -> tuple[Store, pathlib.Path]:
    store = Store(tmp_path / "store")
    store.init()
    target = tmp_path / "muse" / "settings.json"
    setup.install(
        moments.HOST_MUSE_CODE,
        target,
        store.root,
        provider=openrouter.PROVIDER,
    )
    return store, target


def _codes(report: doctor.Report) -> dict[str, doctor.Check]:
    return {check.code: check for check in report.checks}


def test_muse_doctor_reports_missing_openrouter_credential(tmp_path, monkeypatch):
    store, target = _provider_target(tmp_path)
    monkeypatch.setattr(setup, "probe", lambda _host: "Muse 1.4")
    monkeypatch.setattr(openrouter, "detect_credential", lambda _env=None: None)
    monkeypatch.setattr(openrouter, "proxy_health", lambda **_kwargs: True)

    report = doctor.run(
        store, moments.HOST_MUSE_CODE, settings_path=target, provider=openrouter.PROVIDER
    )

    assert "OPENROUTER_CREDENTIAL_MISSING" in _codes(report)
    assert report.status == doctor.FAILED


@pytest.mark.parametrize(
    ("preflight_code", "expected"),
    [
        ("OPENROUTER_AUTH_FAILED", "OPENROUTER_AUTH_FAILED"),
        ("MODEL_NOT_FOUND", "MODEL_NOT_FOUND"),
        ("MODEL_NOT_AVAILABLE", "MODEL_NOT_AVAILABLE"),
    ],
)
def test_muse_doctor_preserves_provider_failure_layer(
    tmp_path, monkeypatch, preflight_code, expected
):
    store, target = _provider_target(tmp_path)
    credential = openrouter.Credential("secret-value", "environment:OPENROUTER_API_KEY")
    monkeypatch.setattr(setup, "probe", lambda _host: "Muse 1.4")
    monkeypatch.setattr(openrouter, "detect_credential", lambda _env=None: credential)
    monkeypatch.setattr(openrouter, "proxy_health", lambda **_kwargs: True)
    monkeypatch.setattr(
        openrouter,
        "openrouter_preflight",
        lambda *_args, **_kwargs: (preflight_code, "classified failure"),
    )

    report = doctor.run(
        store, moments.HOST_MUSE_CODE, settings_path=target, provider=openrouter.PROVIDER
    )

    assert expected in _codes(report)
    assert report.status == doctor.FAILED


def test_muse_doctor_reports_proxy_unavailable_separately(tmp_path, monkeypatch):
    store, target = _provider_target(tmp_path)
    credential = openrouter.Credential("secret-value", "environment:OPENROUTER_API_KEY")
    monkeypatch.setattr(setup, "probe", lambda _host: "Muse 1.4")
    monkeypatch.setattr(openrouter, "detect_credential", lambda _env=None: credential)
    monkeypatch.setattr(openrouter, "proxy_health", lambda **_kwargs: False)
    monkeypatch.setattr(
        openrouter, "openrouter_preflight", lambda *_args, **_kwargs: (None, "ok")
    )

    report = doctor.run(
        store, moments.HOST_MUSE_CODE, settings_path=target, provider=openrouter.PROVIDER
    )

    assert "PROXY_UNREACHABLE" in _codes(report)
    assert report.status == doctor.FAILED


def test_secret_redaction_covers_explicit_and_openrouter_shaped_values():
    secret = "sk-or-v1-super-secret"
    rendered = openrouter.redact(f"credential={secret} secondary=sk-or-another-secret", secret)
    assert secret not in rendered
    assert "sk-or-another-secret" not in rendered
    assert rendered.count("[REDACTED]") == 2


def test_muse_preprovisioned_meta_credential_is_detected_without_reconfiguration(tmp_path):
    config = tmp_path / "config"
    auth = config / "muse" / "auth.json"
    auth.parent.mkdir(parents=True)
    auth.write_text(
        json.dumps({"providers": {"meta": {"api_key": "existing-secret"}}}),
        encoding="utf-8",
    )
    original = auth.read_bytes()

    credential = openrouter.detect_credential(
        {"HOME": str(tmp_path / "home"), "XDG_CONFIG_HOME": str(config)}
    )

    assert credential is not None
    assert credential.source == "muse-auth:meta"
    assert credential.pass_through
    assert auth.read_bytes() == original


def test_missing_pproxy_returns_the_pinned_install_command(monkeypatch):
    credential = openrouter.Credential("existing-secret", "muse-auth:meta")
    monkeypatch.setattr(openrouter, "proxy_health", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(openrouter, "proxy_binary", lambda *_args, **_kwargs: None)

    result = openrouter.ensure_proxy(credential, environment={"HOME": "/tmp/test-home"})

    assert not result.ready
    assert result.command == openrouter.PPROXY_INSTALL
    assert "existing-secret" not in result.detail
    assert "existing-secret" not in result.command


def test_muse_live_failure_never_includes_the_credential(monkeypatch):
    secret = "sk-or-v1-super-secret"
    credential = openrouter.Credential(secret, "environment:OPENROUTER_API_KEY")
    monkeypatch.setattr(openrouter.shutil, "which", lambda *_args, **_kwargs: "/bin/muse")
    monkeypatch.setattr(
        openrouter.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 1, "", f"bad {secret}"),
    )

    code, detail = openrouter.muse_live_preflight(credential)

    assert code == "REASONER_UNAVAILABLE"
    assert secret not in detail


def test_host_reasoner_failure_prevents_ready(tmp_path, monkeypatch):
    store = Store(tmp_path / "store")
    target = tmp_path / "codex" / "hooks.json"
    monkeypatch.setattr(setup, "probe", lambda _host: "codex 1.0")
    monkeypatch.setattr(
        doctor,
        "_live_reasoner_check",
        lambda _store, _host: doctor.Check(
            "REASONER_UNAVAILABLE", False, "live reasoner returned no READY"
        ),
    )

    result = host_setup.run(store, moments.HOST_CODEX, settings_path=target)

    assert result["status"] == doctor.FAILED
    assert "REASONER_UNAVAILABLE" in {
        check["code"] for check in result["checks"]
    }


def test_codex_doctor_flags_disabled_hooks_read_only_sandbox_and_store_failure(
    tmp_path, monkeypatch
):
    store = Store(tmp_path / "store")
    store.init()
    target = tmp_path / "home" / ".codex" / "hooks.json"
    setup.install(moments.HOST_CODEX, target, store.root)
    target.with_name("config.toml").write_text(
        'sandbox_mode = "read-only"\n[features]\nhooks = false\n', encoding="utf-8"
    )
    monkeypatch.setattr(setup, "probe", lambda _host: "codex 1.0")
    monkeypatch.setattr(
        doctor.tempfile,
        "mkstemp",
        lambda **_kwargs: (_ for _ in ()).throw(PermissionError("denied")),
    )

    report = doctor.run(store, moments.HOST_CODEX, settings_path=target)
    codes = _codes(report)

    assert "STORE_NOT_WRITABLE" in codes
    assert "HOOK_INVALID" in codes
    assert "CODEX_SANDBOX_STORE_ACCESS" in codes
    assert "CODEX_HOOK_TRUST_REVIEW" in codes
    assert report.status == doctor.FAILED
