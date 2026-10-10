"""The SDK launcher owns Muse, generated configuration, and its provider bridge."""

from __future__ import annotations

import json
import os
import pathlib
import signal
import sys
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from agent_memory.adapters import moments, muse_launcher, openrouter, setup
from agent_memory.core.config import EXECUTOR_ENV_VAR


class _UpstreamHandler(BaseHTTPRequestHandler):
    requests: list[dict[str, object]] = []

    def log_message(self, _format, *_args):
        return

    def do_POST(self):
        size = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(size)
        self.requests.append(
            {
                "path": self.path,
                "authorization": self.headers.get("Authorization"),
                "body": json.loads(body),
            }
        )
        payload = json.dumps({"forwarded": True}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def test_openrouter_bridge_supplies_muse_catalog_and_forwards_without_leaking_key():
    _UpstreamHandler.requests = []
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), _UpstreamHandler)
    thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    thread.start()
    upstream_url = f"http://127.0.0.1:{upstream.server_port}"
    credential = openrouter.Credential("secret-value", "environment:OPENROUTER_API_KEY")

    try:
        with muse_launcher.OpenRouterBridge(
            credential, openrouter.DEFAULT_MODEL, upstream_url=upstream_url
        ) as bridge:
            with urllib.request.urlopen(f"{bridge.base_url}/muse-code/models") as response:
                catalog = json.load(response)
            request = urllib.request.Request(
                f"{bridge.base_url}/responses",
                data=json.dumps({"model": openrouter.DEFAULT_MODEL, "input": "hello"}).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request) as response:
                forwarded = json.load(response)
    finally:
        upstream.shutdown()
        upstream.server_close()
        thread.join(timeout=2)

    assert [row["id"] for row in catalog["data"]] == [openrouter.DEFAULT_MODEL]
    assert forwarded == {"forwarded": True}
    assert _UpstreamHandler.requests == [
        {
            "path": "/responses",
            "authorization": "Bearer secret-value",
            "body": {"model": openrouter.DEFAULT_MODEL, "input": "hello"},
        }
    ]
    assert "secret-value" not in json.dumps(catalog)


class _Bridge:
    instances: list[_Bridge] = []

    def __init__(self, credential, model):
        self.credential = credential
        self.model = model
        self.base_url = "http://127.0.0.1:43210"
        self.closed = False
        self.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.closed = True


def _fake_muse(tmp_path: pathlib.Path) -> pathlib.Path:
    binary = tmp_path / "real-muse"
    binary.write_text(
        f"#!{sys.executable}\n"
        "import json, os, pathlib, sys\n"
        "config = pathlib.Path(os.environ['XDG_CONFIG_HOME'])\n"
        "settings = config / 'muse' / 'settings.json'\n"
        "auth = pathlib.Path(os.environ['MUSE_AUTH_PATH'])\n"
        "payload = {\n"
        "  'args': sys.argv[1:],\n"
        "  'settings': json.loads(settings.read_text()),\n"
        "  'auth': json.loads(auth.read_text()),\n"
        "  'auth_mode': auth.stat().st_mode & 0o777,\n"
        "  'settings_env': os.environ['AGENT_MEMORY_MUSE_SETTINGS'],\n"
        "}\n"
        "pathlib.Path(os.environ['MUSE_LAUNCH_OBSERVATION']).write_text(json.dumps(payload))\n",
        encoding="utf-8",
    )
    binary.chmod(0o755)
    return binary


def _environment(tmp_path: pathlib.Path, binary: pathlib.Path) -> dict[str, str]:
    return {
        "HOME": str(tmp_path / "home"),
        "XDG_CONFIG_HOME": str(tmp_path / "user-config"),
        "XDG_DATA_HOME": str(tmp_path / "data"),
        "XDG_STATE_HOME": str(tmp_path / "state"),
        "AGENT_MEMORY_STORE": str(tmp_path / "store"),
        "AGENT_MEMORY_MUSE_BINARY": str(binary),
        "OPENROUTER_API_KEY": "secret-value",
        "MUSE_LAUNCH_OBSERVATION": str(tmp_path / "observed.json"),
        "PATH": os.environ.get("PATH", ""),
    }


def test_sdk_launcher_builds_isolated_complete_config_and_cleans_up(tmp_path, monkeypatch):
    _Bridge.instances = []
    binary = _fake_muse(tmp_path)
    environment = _environment(tmp_path, binary)
    user_settings = tmp_path / "user-config" / "muse" / "settings.json"
    user_settings.parent.mkdir(parents=True)
    user_settings.write_text('{"theme":"untouched"}\n', encoding="utf-8")
    mcp = tmp_path / "bin" / "mem-mcp"
    mcp.parent.mkdir()
    mcp.touch()
    mcp.chmod(0o755)
    monkeypatch.setattr(muse_launcher, "OpenRouterBridge", _Bridge)
    monkeypatch.setattr(setup, "mcp_binary", lambda: str(mcp))

    code = muse_launcher.run(["serve"], environment=environment)

    observed = json.loads((tmp_path / "observed.json").read_text(encoding="utf-8"))
    settings = observed["settings"]
    assert code == 0
    assert observed["args"] == ["serve"]
    assert settings["provider"] == openrouter.MUSE_PROVIDER
    assert settings["model"] == openrouter.DEFAULT_MODEL.removeprefix("meta/")
    assert settings["endpoint_transport"] == {
        "base_url": _Bridge.instances[0].base_url,
        "auth": "bearer",
    }
    assert set(settings["hooks"]) == set(moments.DIALECTS[moments.HOST_MUSE_CODE])
    rendered_hooks = json.dumps(settings["hooks"])
    assert "--muse-launcher" in rendered_hooks
    assert str(pathlib.Path(sys.executable).parent / "mem-muse") in rendered_hooks
    assert "--muse-binary" in rendered_hooks
    assert str(binary.resolve()) in rendered_hooks
    assert settings["mcp_servers"][setup.MCP_SERVER]["command"] == str(mcp)
    assert observed["auth"] == {
        "schema_version": 1,
        "providers": {openrouter.MUSE_PROVIDER: {"api_key": "secret-value"}},
    }
    assert observed["auth_mode"] == 0o600
    assert observed["settings_env"].endswith("/muse/settings.json")
    assert _Bridge.instances[0].closed
    assert user_settings.read_text(encoding="utf-8") == '{"theme":"untouched"}\n'
    runtime = tmp_path / "state" / "agent-memory" / "muse-sdk"
    assert not runtime.exists() or not list(runtime.iterdir())


def test_background_exec_gets_a_fresh_owned_bridge(tmp_path, monkeypatch):
    _Bridge.instances = []
    binary = _fake_muse(tmp_path)
    environment = _environment(tmp_path, binary)
    environment[EXECUTOR_ENV_VAR] = "1"
    monkeypatch.setattr(muse_launcher, "OpenRouterBridge", _Bridge)
    monkeypatch.setattr(setup, "mcp_binary", lambda: str(tmp_path / "missing-mem-mcp"))

    code = muse_launcher.run(["exec", "distill this"], environment=environment)

    observed = json.loads((tmp_path / "observed.json").read_text(encoding="utf-8"))
    assert code == 0
    assert observed["args"] == ["exec", "distill this"]
    assert "mcp_servers" not in observed["settings"]
    assert "hooks" not in observed["settings"]
    assert len(_Bridge.instances) == 1
    assert _Bridge.instances[0].closed


def test_launcher_uses_existing_muse_auth_without_rewriting_it(tmp_path, monkeypatch):
    _Bridge.instances = []
    binary = _fake_muse(tmp_path)
    environment = _environment(tmp_path, binary)
    environment.pop("OPENROUTER_API_KEY")
    auth = tmp_path / "user-config" / "muse" / "auth.json"
    auth.parent.mkdir(parents=True)
    auth.write_text('{"providers":{"meta":{"api_key":"stored-secret"}}}\n', encoding="utf-8")
    original = auth.read_bytes()
    monkeypatch.setattr(muse_launcher, "OpenRouterBridge", _Bridge)
    monkeypatch.setattr(setup, "mcp_binary", lambda: str(tmp_path / "missing-mem-mcp"))

    code = muse_launcher.run(["serve"], environment=environment)

    assert code == 0
    assert _Bridge.instances[0].credential.value == "stored-secret"
    assert auth.read_bytes() == original


def test_launcher_reports_missing_credential_before_starting_muse(tmp_path, capsys):
    binary = _fake_muse(tmp_path)
    environment = _environment(tmp_path, binary)
    environment.pop("OPENROUTER_API_KEY")

    code = muse_launcher.run(["serve"], environment=environment)

    captured = capsys.readouterr()
    assert code == muse_launcher.EXIT_CONFIGURATION
    assert "OPENROUTER_CREDENTIAL_MISSING" in captured.err
    assert "muse auth" in captured.err
    assert "secret" not in captured.err
    assert not (tmp_path / "observed.json").exists()


def test_launcher_reports_missing_real_muse_binary(tmp_path, capsys):
    environment = _environment(tmp_path, tmp_path / "missing-muse")

    code = muse_launcher.run(["serve"], environment=environment)

    captured = capsys.readouterr()
    assert code == muse_launcher.EXIT_CONFIGURATION
    assert "HOST_BINARY_MISSING" in captured.err
    assert not (tmp_path / "observed.json").exists()


def test_non_backend_commands_pass_through_without_provider_setup(tmp_path):
    binary = tmp_path / "real-muse"
    binary.write_text(f"#!{sys.executable}\nimport sys\nsys.exit(7)\n", encoding="utf-8")
    binary.chmod(0o755)
    environment = {
        "AGENT_MEMORY_MUSE_BINARY": str(binary),
        "PATH": os.environ.get("PATH", ""),
    }

    code = muse_launcher.run(["--version"], environment=environment)

    assert code == 7


def test_launcher_forwards_shutdown_signal_to_owned_muse(monkeypatch):
    installed = {}

    class Process:
        sent = []

        def poll(self):
            return None

        def send_signal(self, selected):
            self.sent.append(selected)

        def wait(self):
            installed[signal.SIGTERM](signal.SIGTERM, None)
            return 143

    monkeypatch.setattr(muse_launcher.signal, "getsignal", lambda _selected: signal.SIG_DFL)

    def install(selected, handler):
        installed[selected] = handler

    monkeypatch.setattr(muse_launcher.signal, "signal", install)
    process = Process()

    code = muse_launcher._wait(process)

    assert code == 143
    assert process.sent == [signal.SIGTERM]
