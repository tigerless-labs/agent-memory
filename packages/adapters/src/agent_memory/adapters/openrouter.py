"""Muse/OpenRouter provider setup without ever rendering a credential."""

from __future__ import annotations

import dataclasses
import json
import os
import pathlib
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

from agent_memory.core.errors import FieldError, ValidationError

PROVIDER = "openrouter"
MUSE_PROVIDER = "meta"
DEFAULT_MODEL = "meta/muse-spark-1.3-contributor"
DEFAULT_PROXY_URL = "http://127.0.0.1:8817"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
PPROXY_INSTALL = (
    "uv tool install 'pproxy @ "
    "git+https://github.com/mattsta/pproxy.git@6f0f951'"
)
SECRET_PATTERN = re.compile(r"sk-or-[A-Za-z0-9_-]+")


@dataclasses.dataclass(frozen=True)
class Credential:
    value: str
    source: str
    auth_path: pathlib.Path | None = None

    @property
    def pass_through(self) -> bool:
        return self.source.startswith("muse-auth:")


@dataclasses.dataclass(frozen=True)
class ProxyStatus:
    ready: bool
    detail: str
    command: str = ""


def auth_path(environment: dict[str, str] | None = None) -> pathlib.Path:
    env = os.environ if environment is None else environment
    home = pathlib.Path(env.get("HOME", "~")).expanduser()
    config = pathlib.Path(env.get("XDG_CONFIG_HOME") or home / ".config")
    return pathlib.Path(env.get("MUSE_AUTH_PATH") or config / "muse" / "auth.json")


def detect_credential(environment: dict[str, str] | None = None) -> Credential | None:
    env = os.environ if environment is None else environment
    supplied = env.get("OPENROUTER_API_KEY", "").strip()
    if supplied:
        return Credential(supplied, "environment:OPENROUTER_API_KEY")
    path = auth_path(dict(env))
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    providers = parsed.get("providers", {}) if isinstance(parsed, dict) else {}
    if not isinstance(providers, dict):
        return None
    for provider in (PROVIDER, MUSE_PROVIDER):
        configured = providers.get(provider)
        value = configured.get("api_key", "") if isinstance(configured, dict) else ""
        if isinstance(value, str) and value.strip():
            return Credential(value.strip(), f"muse-auth:{provider}", path)
    return None


def merge_routing(
    settings: dict[str, object],
    *,
    provider: str,
    model: str | None = None,
    proxy_url: str = DEFAULT_PROXY_URL,
) -> None:
    if provider != PROVIDER:
        raise ValidationError(
            [FieldError("provider", f"unsupported provider {provider!r}; choose {PROVIDER}")]
        )
    target = model or DEFAULT_MODEL
    muse_model = target.removeprefix(f"{MUSE_PROVIDER}/")
    expected: dict[str, object] = {
        "provider": MUSE_PROVIDER,
        "model": muse_model,
        "endpoint_transport": {"base_url": proxy_url, "auth": "bearer"},
    }
    for key, value in expected.items():
        existing = settings.get(key)
        if existing is not None and existing != value:
            raise ValidationError(
                [
                    FieldError(
                        f"settings.{key}",
                        "already has a different value; left unchanged to protect user config",
                    )
                ]
            )
        settings[key] = value


def proxy_binary(environment: dict[str, str] | None = None) -> str | None:
    env = os.environ if environment is None else environment
    explicit = env.get("AGENT_MEMORY_PPROXY", "").strip()
    candidate = explicit or shutil.which("pproxy", path=env.get("PATH"))
    if not candidate:
        return None
    try:
        completed = subprocess.run(
            [candidate, "--help"], capture_output=True, text=True, timeout=10, check=False, env=env
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    help_text = completed.stdout + completed.stderr
    return candidate if completed.returncode == 0 and "--auth-passthrough" in help_text else None


def ensure_proxy(
    credential: Credential,
    *,
    environment: dict[str, str] | None = None,
    proxy_url: str = DEFAULT_PROXY_URL,
) -> ProxyStatus:
    env = _network_environment(environment)
    if proxy_health(proxy_url, environment=env):
        return ProxyStatus(True, f"reachable at {proxy_url}")
    binary = proxy_binary(env)
    if not binary:
        return ProxyStatus(False, "pproxy is not installed", PPROXY_INSTALL)
    parsed = urllib.parse.urlsplit(proxy_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 8817
    command = [binary, "--host", host, "--port", str(port), "--model-filter", "muse-spark"]
    if credential.pass_through:
        command.append("--auth-passthrough")
        env.pop("OPENROUTER_API_KEY", None)
    else:
        env["OPENROUTER_API_KEY"] = credential.value
    state = _state_home(env) / "agent-memory"
    state.mkdir(parents=True, exist_ok=True)
    log_path = state / "pproxy.log"
    pid_path = state / "pproxy.pid"
    try:
        with log_path.open("a", encoding="utf-8") as log:
            process = subprocess.Popen(
                command,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                text=True,
            )
        pid_path.write_text(f"{process.pid}\n", encoding="utf-8")
    except OSError as error:
        return ProxyStatus(False, f"could not start pproxy: {error}", PPROXY_INSTALL)
    for _ in range(24):
        if proxy_health(proxy_url, environment=env):
            return ProxyStatus(True, f"started at {proxy_url}")
        if process.poll() is not None:
            return ProxyStatus(False, f"pproxy exited with code {process.returncode}")
        time.sleep(0.25)
    return ProxyStatus(False, f"pproxy did not become ready at {proxy_url}")


def proxy_health(
    proxy_url: str = DEFAULT_PROXY_URL, *, environment: dict[str, str] | None = None
) -> bool:
    try:
        status, payload = request_json(
            f"{proxy_url.rstrip('/')}/healthz", timeout=2, environment=environment
        )
    except OSError:
        return False
    return status == 200 and payload.get("ok") is True


def openrouter_preflight(
    credential: Credential,
    *,
    model: str | None = None,
    environment: dict[str, str] | None = None,
) -> tuple[str | None, str]:
    target = model or DEFAULT_MODEL
    headers = {"Authorization": f"Bearer {credential.value}"}
    try:
        status, _ = request_json(
            f"{OPENROUTER_BASE_URL}/auth/key",
            headers=headers,
            timeout=15,
            environment=environment,
        )
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            return "OPENROUTER_AUTH_FAILED", f"OpenRouter rejected the credential ({error.code})"
        return "OPENROUTER_AUTH_FAILED", f"OpenRouter auth check returned HTTP {error.code}"
    except OSError as error:
        return "PROXY_UNREACHABLE", f"OpenRouter auth check could not connect: {error}"
    if status != 200:
        return "OPENROUTER_AUTH_FAILED", f"OpenRouter auth check returned HTTP {status}"
    try:
        status, payload = request_json(
            f"{OPENROUTER_BASE_URL}/models",
            headers=headers,
            timeout=20,
            environment=environment,
        )
    except (OSError, urllib.error.HTTPError) as error:
        return "PROXY_UNREACHABLE", f"OpenRouter model catalog could not be read: {error}"
    raw_rows = payload.get("data", []) if isinstance(payload, dict) else []
    rows = raw_rows if isinstance(raw_rows, list) else []
    ids = {
        str(row.get("id"))
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    }
    if status != 200 or target not in ids:
        return "MODEL_NOT_FOUND", f"target model {target!r} is not in the OpenRouter catalog"
    try:
        status, _ = request_json(
            f"{OPENROUTER_BASE_URL}/responses",
            headers={**headers, "Content-Type": "application/json"},
            data={
                "model": target,
                "input": "Reply with exactly READY.",
                "max_output_tokens": 16,
                "stream": False,
            },
            timeout=30,
            environment=environment,
        )
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            code = "OPENROUTER_AUTH_FAILED" if error.code == 401 else "MODEL_NOT_AVAILABLE"
            return code, f"OpenRouter model preflight returned HTTP {error.code}"
        if error.code == 404:
            return "MODEL_NOT_FOUND", f"OpenRouter model preflight returned HTTP {error.code}"
        return "REASONER_UNAVAILABLE", f"OpenRouter model preflight returned HTTP {error.code}"
    except OSError as error:
        return "PROXY_UNREACHABLE", f"OpenRouter model preflight could not connect: {error}"
    if status != 200:
        return "REASONER_UNAVAILABLE", f"OpenRouter model preflight returned HTTP {status}"
    return None, f"credential accepted and target model {target!r} exists"


def muse_live_preflight(
    credential: Credential,
    *,
    model: str | None = None,
    environment: dict[str, str] | None = None,
    proxy_url: str = DEFAULT_PROXY_URL,
    timeout: float = 60,
) -> tuple[str | None, str]:
    binary = shutil.which("muse", path=(environment or os.environ).get("PATH"))
    if not binary:
        return "HOST_BINARY_MISSING", "muse is not on PATH"
    target = model or DEFAULT_MODEL
    env = _network_environment(environment)
    env["MUSE_NO_AUTO_UPDATE"] = "1"
    env["META_API_KEY"] = credential.value
    command = [
        binary,
        "exec",
        "--provider",
        MUSE_PROVIDER,
        "--base-url",
        proxy_url,
        "--model",
        target,
        "--no-session-log",
        "--disable-shell",
        "Reply with exactly READY.",
    ]
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, check=False, timeout=timeout, env=env
        )
    except subprocess.TimeoutExpired as error:
        output = redact(_as_text(error.stdout) + _as_text(error.stderr), credential.value)
        detail = "Muse live request timed out"
        if "retrying" in output:
            detail += " after upstream retries"
        return "REASONER_UNAVAILABLE", detail
    output = redact(completed.stdout + completed.stderr, credential.value)
    if completed.returncode == 0 and "READY" in output:
        return None, "Muse completed a live request through pproxy and OpenRouter"
    lowered = output.lower()
    if "401" in lowered or "unauthorized" in lowered or "invalid api key" in lowered:
        return "OPENROUTER_AUTH_FAILED", "Muse live request was rejected by OpenRouter auth"
    if "403" in lowered or "not available in your region" in lowered:
        return "MODEL_NOT_AVAILABLE", "target model is not available from this region/account"
    return "REASONER_UNAVAILABLE", "Muse live request did not complete successfully"


def request_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    data: dict[str, object] | None = None,
    timeout: float = 10,
    environment: dict[str, str] | None = None,
) -> tuple[int, dict[str, object]]:
    body = json.dumps(data).encode() if data is not None else None
    request = urllib.request.Request(url, headers=headers or {}, data=body)
    proxies: dict[str, str] = {}
    env = os.environ if environment is None else environment
    for scheme in ("http", "https"):
        configured = env.get(f"{scheme.upper()}_PROXY") or env.get(f"{scheme}_proxy")
        if configured:
            parsed = urllib.parse.urlsplit(configured)
            if parsed.hostname:
                proxies[scheme] = configured
            else:
                proxies.pop(scheme, None)
    if urllib.parse.urlsplit(url).hostname in {"127.0.0.1", "localhost"}:
        proxies = {}
    opener = urllib.request.build_opener(urllib.request.ProxyHandler(proxies))
    with opener.open(request, timeout=timeout) as response:
        raw = response.read()
        parsed = json.loads(raw) if raw else {}
        return int(response.status), parsed if isinstance(parsed, dict) else {}


def redact(text: str, *secrets: str) -> str:
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return SECRET_PATTERN.sub("[REDACTED]", text)


def _network_environment(environment: dict[str, str] | None) -> dict[str, str]:
    env = dict(os.environ if environment is None else environment)
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        value = env.get(name)
        if value and not urllib.parse.urlsplit(value).hostname:
            env.pop(name, None)
    return env


def _state_home(environment: dict[str, str]) -> pathlib.Path:
    home = pathlib.Path(environment.get("HOME", "~")).expanduser()
    return pathlib.Path(environment.get("XDG_STATE_HOME") or home / ".local" / "state")


def _as_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode(errors="replace") if isinstance(value, bytes) else value
