"""Two ways to supply the reading a sleep needs, both outside the core (Invariant 5).

They fail differently, which is why both exist. A host reasoner spends the agent the user is
already running: no key, no second bill, and the reasoning shows up in that agent's own
transcript where it can be read. An endpoint reasoner answers on a cron at three in the
morning when no agent session exists, at the cost of a credential and a network hop.

Neither carries algorithm. Text goes out, text comes back, and everything about which text is
worth sending — and which of the reply to believe — stays in the core.
"""

from __future__ import annotations

import dataclasses
import json
import os
import pathlib
import shutil
import tempfile
import urllib.error
import urllib.request
from typing import TYPE_CHECKING

from agent_memory.core.config import EXECUTOR_ENV_VAR
from agent_memory.core.errors import ReasonerUnavailableError

from .credentials import API_KEY_ENV, BASE_URL_ENV, VertexCredentials
from .hosts import BINARIES, HOST_CLAUDE_CODE, Host, HostResult, HostSpec

if TYPE_CHECKING:
    from .app_server import CodexAppServerSession

CHAT_COMPLETIONS = "/chat/completions"
DEFAULT_ENDPOINT_MODEL = "google/gemini-2.5-flash"
DEFAULT_TIMEOUT_SECONDS = 120.0
ROLE_USER = "user"
EMPTY = ""
CLAUDE_BUNDLED_ENV = "CLAUDE_CODE_EXECPATH"


@dataclasses.dataclass
class HostReasoner:
    """The consuming agent's own CLI, run headless for one turn."""

    host: Host
    max_turns: int = 1

    def __call__(self, prompt: str) -> str:
        result = self.host.run(
            prompt,
            tools_enabled=False,
            max_turns=self.max_turns,
            environment={EXECUTOR_ENV_VAR: "1"},
        )
        if not result.ok:
            name = getattr(self.host, "name", "configured host")
            detail = f": {result.error.strip()}" if result.error.strip() else ""
            raise ReasonerUnavailableError(
                f"host reasoner failed for {name}{detail}; run mem doctor --host {name}"
            )
        if not result.text.strip():
            name = getattr(self.host, "name", "configured host")
            raise ReasonerUnavailableError(
                f"host reasoner returned an empty response for {name}"
            )
        return result.text

    @classmethod
    def for_host(cls, name: str, model: str = EMPTY) -> HostReasoner:
        """A host is named by its dialect, not by its binary — `claude-code` runs `claude`."""
        if name not in BINARIES:
            raise ReasonerUnavailableError(f"unsupported host reasoner {name!r}")
        binary, default_model = BINARIES[name]
        bundled = os.environ.get(CLAUDE_BUNDLED_ENV, EMPTY)
        if name == HOST_CLAUDE_CODE and bundled and shutil.which(binary) is None:
            binary = bundled
        return cls(host=Host(HostSpec(name=name, binary=binary, model=model or default_model)))


@dataclasses.dataclass
class HostReasonerRun:
    """One Codex thread and its isolated local session store."""

    host: Host
    opening: str
    _scratch: tempfile.TemporaryDirectory[str] = dataclasses.field(init=False)
    _environment: dict[str, str] = dataclasses.field(init=False)
    _session_id: str = dataclasses.field(default="", init=False)
    _closed: bool = dataclasses.field(default=False, init=False)
    results: list[HostResult] = dataclasses.field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self._scratch = tempfile.TemporaryDirectory()
        self._environment = self.host.isolated_codex_environment(
            {EXECUTOR_ENV_VAR: "1"}, pathlib.Path(self._scratch.name)
        )

    def step(self, prompt: str) -> str:
        if self._closed:
            raise ReasonerUnavailableError("reasoner session is already closed")
        payload = prompt
        if not self._session_id:
            payload = self.opening + (("\n\n" + prompt) if prompt else "")
        result = self.host.run_session(
            payload, session_id=self._session_id, environment=self._environment
        )
        self.results.append(result)
        if not self._session_id and result.session_id:
            self._session_id = result.session_id
        return _require_host_reply(self.host, result)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._scratch.cleanup()


@dataclasses.dataclass
class StatefulHostReasoner:
    """A Host reasoner whose Write rounds share one isolated Codex thread."""

    host: Host
    max_turns: int = 1

    def __call__(self, prompt: str) -> str:
        return HostReasoner(self.host, self.max_turns)(prompt)

    def begin(self, opening: str) -> HostReasonerRun:
        return HostReasonerRun(self.host, opening)

    @classmethod
    def for_host(cls, name: str, model: str = EMPTY) -> StatefulHostReasoner:
        selected = HostReasoner.for_host(name, model)
        return cls(selected.host)


@dataclasses.dataclass
class AppServerHostReasonerRun:
    """One Codex process and ephemeral thread for one Write batch."""

    host: Host
    opening: str
    _session: CodexAppServerSession = dataclasses.field(init=False)
    _first: bool = dataclasses.field(default=True, init=False)
    _closed: bool = dataclasses.field(default=False, init=False)
    results: list[HostResult] = dataclasses.field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self._session = self.host.open_app_server()

    def step(self, prompt: str) -> str:
        if self._closed:
            raise ReasonerUnavailableError("reasoner session is already closed")
        payload = self.opening + (("\n\n" + prompt) if prompt else "") if self._first else prompt
        self._first = False
        result = self._session.step(payload)
        self.results.append(result)
        return _require_host_reply(self.host, result)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._session.close()


@dataclasses.dataclass
class AppServerHostReasoner:
    """A Codex reasoner whose Write rounds share one short-lived process."""

    host: Host
    max_turns: int = 1

    def __call__(self, prompt: str) -> str:
        return HostReasoner(self.host, self.max_turns)(prompt)

    def begin(self, opening: str) -> AppServerHostReasonerRun:
        return AppServerHostReasonerRun(self.host, opening)

    @classmethod
    def for_host(cls, name: str, model: str = EMPTY) -> AppServerHostReasoner:
        selected = HostReasoner.for_host(name, model)
        return cls(selected.host)


@dataclasses.dataclass
class EndpointReasoner:
    """An OpenAI-shaped chat endpoint, credentialed the way the hosts already are."""

    model: str = DEFAULT_ENDPOINT_MODEL
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    credentials: VertexCredentials = dataclasses.field(default_factory=VertexCredentials)
    base_url: str = EMPTY

    def __call__(self, prompt: str) -> str:
        environment = dict(os.environ)
        base = self.base_url or environment.get(BASE_URL_ENV, EMPTY)
        key = environment.get(API_KEY_ENV, EMPTY)
        if not base:
            supplied = self.credentials.environment(preserve_api_key=False)
            base = supplied.get(BASE_URL_ENV, EMPTY)
            key = supplied.get(API_KEY_ENV, EMPTY)
        elif not key:
            supplied = self.credentials.environment()
            key = supplied.get(API_KEY_ENV, EMPTY)
        if not base:
            raise ReasonerUnavailableError(
                "endpoint reasoner requires executor.endpoint or a Google Cloud project"
            )
        if not key:
            raise ReasonerUnavailableError(
                "endpoint reasoner requires GEMINI_API_KEY or gcloud authentication"
            )
        request = urllib.request.Request(
            base.rstrip("/") + CHAT_COMPLETIONS,
            data=json.dumps(
                {"model": self.model, "messages": [{"role": ROLE_USER, "content": prompt}]}
            ).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except json.JSONDecodeError as error:
            raise ReasonerUnavailableError("endpoint returned invalid JSON") from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise ReasonerUnavailableError("endpoint request failed") from error
        message = _first_message(payload)
        if not message.strip():
            raise ReasonerUnavailableError("endpoint returned no valid message")
        return message


def _first_message(payload: object) -> str:
    if not isinstance(payload, dict):
        return EMPTY
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return EMPTY
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    return content if isinstance(content, str) else EMPTY


def _require_host_reply(host: Host, result: HostResult) -> str:
    if not result.ok:
        name = getattr(host, "name", "configured host")
        detail = f": {result.error.strip()}" if result.error.strip() else ""
        raise ReasonerUnavailableError(
            f"host reasoner session failed for {name}{detail}; run mem doctor --host {name}"
        )
    if not result.text.strip():
        name = getattr(host, "name", "configured host")
        raise ReasonerUnavailableError(
            f"host reasoner session returned an empty response for {name}"
        )
    return result.text
