"""Two ways to supply the reading a sleep needs, both outside the core (Invariant 5).

They fail differently, which is why both exist. A host reasoner spends the agent the user is
already running: no key, no second bill, and the reasoning shows up in that agent's own
transcript where it can be read. An endpoint reasoner answers on a cron at three in the
morning when no agent session exists, at the cost of a credential and a network hop.

Neither carries algorithm. For Write negotiation both run as standard tool-use agents over the
core's Write toolkit — the endpoint through native function calling in a loop the executor
drives, the host through its own loop with the toolkit served over MCP. Everything about what
a tool does and which operations to believe stays in the core.
"""

from __future__ import annotations

import dataclasses
import json
import os
import pathlib
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.request

from agent_memory.core.config import EXECUTOR_ENV_VAR
from agent_memory.core.errors import ReasonerUnavailableError
from agent_memory.core.manage_toolkit import ManageReviewToolkit
from agent_memory.core.reasoning import ReviewRuntime
from agent_memory.core.toolkit import WriteToolkit

from .credentials import API_KEY_ENV, BASE_URL_ENV, VertexCredentials
from .hosts import BINARIES, HOST_CLAUDE_CODE, Host, HostResult, HostSpec, ToolServer

CHAT_COMPLETIONS = "/chat/completions"
DEFAULT_ENDPOINT_MODEL = "google/gemini-2.5-flash"
DEFAULT_TIMEOUT_SECONDS = 120.0
DEFAULT_ENDPOINT_ATTEMPTS = 3
ROLE_SYSTEM = "system"
ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"
ROLE_TOOL = "tool"
EMPTY = ""
TOOL_SERVER_NAME = "memory"
WRITE_SESSION_MODULE = "agent_memory.mcp.write_session"
MANAGE_SESSION_MODULE = "agent_memory.mcp.manage_session"
MANAGE_TOOL_SERVER_NAME = "memory_review"
MALFORMED_ARGUMENTS = "tool arguments must be a JSON object"
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
            raise _host_failure(self.host, result)
        if not result.text.strip():
            name = getattr(self.host, "name", "configured host")
            raise ReasonerUnavailableError(f"host reasoner returned an empty response for {name}")
        return result.text

    @classmethod
    def for_host(
        cls,
        name: str,
        model: str = EMPTY,
        provider: str = EMPTY,
        allow_data_training: bool = False,
    ) -> HostReasoner:
        """A host is named by its dialect, not by its binary — `claude-code` runs `claude`."""
        if name not in BINARIES:
            raise ReasonerUnavailableError(f"unsupported host reasoner {name!r}")
        binary, default_model = BINARIES[name]
        bundled = os.environ.get(CLAUDE_BUNDLED_ENV, EMPTY)
        if name == HOST_CLAUDE_CODE and bundled and shutil.which(binary) is None:
            binary = bundled
        return cls(
            host=Host(
                HostSpec(
                    name=name,
                    binary=binary,
                    model=model or default_model,
                    provider=provider,
                    allow_data_training=allow_data_training,
                )
            )
        )


@dataclasses.dataclass
class ToolHostReasoner(HostReasoner):
    """The host CLI as a tool-use agent: one run per batch, the toolkit served over MCP."""

    def converse(self, instructions: str, material: str, toolkit: WriteToolkit) -> None:
        self._converse(
            instructions,
            material,
            toolkit,
            server_name=TOOL_SERVER_NAME,
            module=WRITE_SESSION_MODULE,
        )

    def review_converse(
        self, instructions: str, material: str, toolkit: ManageReviewToolkit
    ) -> ReviewRuntime:
        """Run one bounded native Manage review and return measured Host wall time."""
        result = self._converse(
            instructions,
            material,
            toolkit,
            server_name=MANAGE_TOOL_SERVER_NAME,
            module=MANAGE_SESSION_MODULE,
            timeout_seconds=toolkit.request.limits.timeout_seconds,
            host_analytics_enabled=False,
        )
        usage = result.usage
        phases = result.phases
        return ReviewRuntime(
            duration_seconds=result.seconds,
            startup_seconds=phases.startup_seconds if phases else None,
            model_wait_seconds=phases.model_wait_seconds if phases else None,
            mcp_seconds=phases.mcp_seconds if phases else None,
            shutdown_seconds=phases.shutdown_seconds if phases else None,
            agent_turns=usage.turns if usage else None,
            input_tokens=usage.input_tokens if usage else None,
            cached_input_tokens=usage.cached_input_tokens if usage else None,
            output_tokens=usage.output_tokens if usage else None,
        )

    def _converse(
        self,
        instructions: str,
        material: str,
        toolkit: WriteToolkit | ManageReviewToolkit,
        *,
        server_name: str,
        module: str,
        timeout_seconds: float | None = None,
        host_analytics_enabled: bool = True,
    ) -> HostResult:
        with tempfile.TemporaryDirectory() as batch:
            directory = pathlib.Path(batch)
            toolkit.save_seed(directory)
            server = ToolServer(
                name=server_name,
                command=sys.executable,
                args=("-m", module, str(directory)),
                tools=tuple(spec.name for spec in toolkit.catalogue()),
                host_analytics_enabled=host_analytics_enabled,
            )
            result = self.host.converse(
                material,
                system_prompt=instructions,
                server=server,
                environment={EXECUTOR_ENV_VAR: "1"},
                timeout_seconds=timeout_seconds,
            )
            if not result.ok:
                raise _host_failure(self.host, result)
            toolkit.absorb_directory(directory)
            return result


def _host_failure(host: Host, result: HostResult) -> ReasonerUnavailableError:
    name = getattr(host, "name", "configured host")
    detail = f": {result.error.strip()}" if result.error.strip() else ""
    return ReasonerUnavailableError(
        f"host reasoner failed for {name}{detail}; run mem doctor --host {name}"
    )


@dataclasses.dataclass
class EndpointReasoner:
    """An OpenAI-shaped chat endpoint, credentialed the way the hosts already are."""

    model: str = DEFAULT_ENDPOINT_MODEL
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    credentials: VertexCredentials = dataclasses.field(default_factory=VertexCredentials)
    base_url: str = EMPTY
    attempts: int = DEFAULT_ENDPOINT_ATTEMPTS

    def __call__(self, prompt: str) -> str:
        failure: Exception | None = None
        for attempt in range(self._tries()):
            try:
                payload = self._post({"model": self.model, "messages": [_message(ROLE_USER, prompt)]})
                message = _first_message(payload)
                if message.strip():
                    return message
                failure = ReasonerUnavailableError("endpoint returned no valid message")
            except ReasonerUnavailableError as error:
                failure = error
            self._pause(attempt)
        raise failure if failure else ReasonerUnavailableError("endpoint returned no valid message")

    def converse(self, instructions: str, material: str, toolkit: WriteToolkit) -> None:
        """The standard loop: call, run every requested tool, answer it, until no tool is asked."""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.schema,
                },
            }
            for spec in toolkit.catalogue()
        ]
        messages: list[dict[str, object]] = [
            _message(ROLE_SYSTEM, instructions),
            _message(ROLE_USER, material),
        ]
        while True:
            body: dict[str, object] = {"model": self.model, "messages": messages, "tools": tools}
            reply = self._reply(body)
            messages.append(reply)
            calls = reply.get("tool_calls")
            if not isinstance(calls, list) or not calls:
                return
            for call in calls:
                messages.append(_answer(call, toolkit))

    def _reply(self, body: dict[str, object]) -> dict[str, object]:
        """One assistant turn, retried only when the request itself failed.

        A dropped connection or a truncated body is worth repeating. A turn that
        arrives with the wrong shape is a protocol mismatch, and a tool call whose
        arguments do not parse is the model's own mistake to correct: the loop
        answers it and lets the model try again. Neither is retried here, so the
        conversation stays exactly as the endpoint saw it.
        """
        failure: Exception | None = None
        for attempt in range(self._tries()):
            try:
                payload = self._post(body)
            except ReasonerUnavailableError as error:
                failure = error
                self._pause(attempt)
                continue
            return _assistant(payload)
        raise failure if failure else ReasonerUnavailableError("endpoint returned no valid message")

    def _tries(self) -> int:
        return max(1, self.attempts)

    def _pause(self, attempt: int) -> None:
        if attempt + 1 < self._tries():
            time.sleep(min(2.0, 0.5 * (attempt + 1)))

    def _post(self, body: dict[str, object]) -> object:
        base, key = self._endpoint()
        request = urllib.request.Request(
            base.rstrip("/") + CHAT_COMPLETIONS,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except json.JSONDecodeError as error:
            raise ReasonerUnavailableError("endpoint returned invalid JSON") from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise ReasonerUnavailableError("endpoint request failed") from error

    def _endpoint(self) -> tuple[str, str]:
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
        return base, key


def _message(role: str, content: str) -> dict[str, object]:
    return {"role": role, "content": content}


def _assistant(payload: object) -> dict[str, object]:
    choices = payload.get("choices") if isinstance(payload, dict) else None
    first = choices[0] if isinstance(choices, list) and choices else None
    message = first.get("message") if isinstance(first, dict) else None
    if not isinstance(message, dict):
        raise ReasonerUnavailableError("endpoint returned no valid message")
    reply: dict[str, object] = {"role": ROLE_ASSISTANT, "content": message.get("content")}
    calls = message.get("tool_calls")
    if isinstance(calls, list) and calls:
        reply["tool_calls"] = calls
    return reply


def _answer(call: object, toolkit: WriteToolkit) -> dict[str, object]:
    described = call if isinstance(call, dict) else {}
    function = described.get("function")
    function = function if isinstance(function, dict) else {}
    try:
        arguments = json.loads(str(function.get("arguments") or "{}"))
    except json.JSONDecodeError:
        arguments = None
    text = (
        toolkit.call(str(function.get("name") or EMPTY), arguments).text
        if isinstance(arguments, dict)
        else MALFORMED_ARGUMENTS
    )
    return {"role": ROLE_TOOL, "tool_call_id": described.get("id"), "content": text}


def _first_message(payload: object) -> str:
    if not isinstance(payload, dict):
        return EMPTY
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return EMPTY
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    return content if isinstance(content, str) else EMPTY
