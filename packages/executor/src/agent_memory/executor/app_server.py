"""A batch-scoped Codex app-server transport for bounded text reasoning."""

from __future__ import annotations

import json
import os
import pathlib
import queue
import subprocess
import tempfile
import threading
import time
import uuid
from collections import Counter
from contextlib import suppress
from typing import Any

from agent_memory.core import observation
from agent_memory.core.config import (
    EXECUTOR_ENV_VAR,
    MUSE_SETTINGS_ENV_VAR,
    STORE_ENV_VAR,
)
from agent_memory.core.errors import ReasonerUnavailableError

from .hosts import HOST_CODEX, Host, HostResult

APP_SERVER_CLIENT_NAME = "agent_memory_write"
APP_SERVER_CLIENT_TITLE = "Agent Memory Write"
APP_SERVER_CLIENT_VERSION = "0.1.0"
APP_SERVER_STDIO = "stdio://"
APP_SERVER_ERROR_EXCERPT = 400
APP_SERVER_DISABLED_FEATURES = (
    "apps",
    "plugins",
    "multi_agent",
    "hooks",
    "memories",
    "shell_tool",
    "unified_exec",
    "skill_search",
    "skill_mcp_dependency_install",
    "browser_use",
    "computer_use",
    "view_image",
    "image_generation",
    "goals",
)
APP_SERVER_ALLOWED_ITEMS = frozenset(("userMessage", "agentMessage", "reasoning"))
APP_SERVER_BASE_INSTRUCTIONS = (
    "You are a bounded memory-distillation reasoner. Follow the supplied protocol exactly and "
    "return only the requested JSON lines. Never use tools, files, commands, plugins, apps, "
    "personal memory, or child agents."
)
APP_SERVER_DEVELOPER_INSTRUCTIONS = (
    "The caller owns all Recall, Read, validation, and Store writes. You only choose the next "
    "JSON request or final JSON operation from supplied text."
)


class CodexAppServerSession:
    """One ephemeral Codex thread over one short-lived app-server process."""

    def __init__(self, host: Host):
        if host.spec.name != HOST_CODEX:
            raise ReasonerUnavailableError("app-server sessions require the Codex host")
        self.host = host
        self.results: list[HostResult] = []
        self.process_starts = 0
        self.startup_seconds = 0.0
        self.model_turn_seconds: list[float | None] = []
        self.event_methods: Counter[str] = Counter()
        self.item_types: Counter[str] = Counter()
        self.thread_id = ""
        self._request_id = 0
        self._closed = False
        self._scratch = tempfile.TemporaryDirectory(prefix="agent-memory-app-server-")
        self._events: queue.Queue[object] = queue.Queue()
        self._stderr: list[str] = []
        self._process: subprocess.Popen[str] | None = None
        try:
            self._start()
        except BaseException:
            self.close()
            raise

    def _start(self) -> None:
        scratch = pathlib.Path(self._scratch.name)
        work = scratch / "work"
        work.mkdir()
        runtime_home = scratch / "home"
        xdg_config = scratch / "xdg-config"
        xdg_data = scratch / "xdg-data"
        xdg_cache = scratch / "xdg-cache"
        for path in (runtime_home, xdg_config, xdg_data, xdg_cache):
            path.mkdir()
        isolated = self.host.isolated_codex_environment({EXECUTOR_ENV_VAR: "1"}, scratch)
        environment = dict(os.environ)
        for name in (
            STORE_ENV_VAR,
            MUSE_SETTINGS_ENV_VAR,
            observation.ENV,
            observation.ATTEMPT_ENV,
        ):
            environment.pop(name, None)
        environment.update(
            isolated
            | {
                "HOME": str(runtime_home),
                "XDG_CONFIG_HOME": str(xdg_config),
                "XDG_DATA_HOME": str(xdg_data),
                "XDG_CACHE_HOME": str(xdg_cache),
            }
        )
        command = [
            self.host.spec.binary,
            "app-server",
            "--listen",
            APP_SERVER_STDIO,
        ]
        for feature in APP_SERVER_DISABLED_FEATURES:
            command.extend(("--disable", feature))
        command.extend(("-c", "project_doc_max_bytes=0"))
        started = time.monotonic()
        try:
            self._process = subprocess.Popen(
                command,
                cwd=work,
                env=environment,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except OSError as error:
            raise ReasonerUnavailableError(f"Codex app-server failed to start: {error}") from error
        self.process_starts += 1
        assert self._process.stdout is not None
        assert self._process.stderr is not None
        stderr = self._process.stderr
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(
            target=lambda: self._stderr.extend(stderr.readlines()), daemon=True
        ).start()
        self._require_response(
            self._request(
                "initialize",
                {
                    "clientInfo": {
                        "name": APP_SERVER_CLIENT_NAME,
                        "title": APP_SERVER_CLIENT_TITLE,
                        "version": APP_SERVER_CLIENT_VERSION,
                    },
                    "capabilities": {"optOutNotificationMethods": ["item/agentMessage/delta"]},
                },
            ),
            "initialize",
        )
        self._notify("initialized", {})
        response = self._request(
            "thread/start",
            {
                "model": self.host.spec.model,
                "cwd": str(work),
                "approvalPolicy": "never",
                "sandbox": "read-only",
                "ephemeral": True,
                "baseInstructions": APP_SERVER_BASE_INSTRUCTIONS,
                "developerInstructions": APP_SERVER_DEVELOPER_INSTRUCTIONS,
            },
        )
        self._require_response(response, "thread/start")
        result = response.get("result")
        thread = result.get("thread") if isinstance(result, dict) else None
        thread_id = thread.get("id") if isinstance(thread, dict) else None
        try:
            self.thread_id = str(uuid.UUID(thread_id)) if isinstance(thread_id, str) else ""
        except ValueError:
            self.thread_id = ""
        if not self.thread_id:
            raise ReasonerUnavailableError("Codex app-server returned no valid thread id")
        if not isinstance(thread, dict) or thread.get("ephemeral") is not True:
            raise ReasonerUnavailableError("Codex app-server thread was not ephemeral")
        self.startup_seconds = time.monotonic() - started

    def _read_stdout(self) -> None:
        process = self._process
        if process is None or process.stdout is None:
            return
        try:
            for line in process.stdout:
                try:
                    self._events.put(json.loads(line))
                except json.JSONDecodeError as error:
                    self._events.put(error)
        finally:
            self._events.put(EOFError("Codex app-server stdout closed"))

    def _send(self, message: dict[str, object]) -> None:
        process = self._process
        if process is None or process.poll() is not None or process.stdin is None:
            code = process.returncode if process is not None else "not started"
            raise ReasonerUnavailableError(
                f"Codex app-server exited ({code}): {self._stderr_text()}"
            )
        try:
            process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
            process.stdin.flush()
        except OSError as error:
            raise ReasonerUnavailableError("Codex app-server input closed") from error

    def _request(self, method: str, params: dict[str, object]) -> dict[str, Any]:
        self._request_id += 1
        request_id = self._request_id
        self._send({"id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + self.host.spec.timeout_seconds
        while True:
            event = self._next_event(deadline)
            if event.get("id") == request_id and "method" not in event:
                return event
            self._observe(event)

    def _notify(self, method: str, params: dict[str, object]) -> None:
        self._send({"method": method, "params": params})

    def _next_event(self, deadline: float) -> dict[str, Any]:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ReasonerUnavailableError("Codex app-server timed out")
        try:
            event = self._events.get(timeout=remaining)
        except queue.Empty as error:
            raise ReasonerUnavailableError("Codex app-server timed out") from error
        if isinstance(event, BaseException):
            raise ReasonerUnavailableError(
                f"Codex app-server protocol failed: {event}; {self._stderr_text()}"
            ) from event
        if not isinstance(event, dict):
            raise ReasonerUnavailableError("Codex app-server returned a non-object event")
        return event

    def _observe(self, event: dict[str, Any]) -> None:
        method = event.get("method")
        if not isinstance(method, str):
            return
        self.event_methods[method] += 1
        if "id" in event:
            raise ReasonerUnavailableError(f"Codex app-server unexpectedly requested {method!r}")
        if method not in ("item/started", "item/completed"):
            return
        params = event.get("params")
        item = params.get("item") if isinstance(params, dict) else None
        item_type = item.get("type") if isinstance(item, dict) else None
        if isinstance(item_type, str):
            self.item_types[item_type] += 1
            if item_type not in APP_SERVER_ALLOWED_ITEMS:
                raise ReasonerUnavailableError(
                    f"Codex app-server attempted forbidden item {item_type!r}"
                )

    @staticmethod
    def _require_response(response: dict[str, Any], method: str) -> None:
        if "error" in response:
            raise ReasonerUnavailableError(f"Codex app-server {method} failed")

    def _stderr_text(self) -> str:
        return "".join(self._stderr).strip()[-APP_SERVER_ERROR_EXCERPT:]

    def step(self, prompt: str) -> HostResult:
        if self._closed:
            return HostResult("", False, 0.0, "reasoner session is already closed")
        started = time.monotonic()
        self._request_id += 1
        request_id = self._request_id
        try:
            self._send(
                {
                    "id": request_id,
                    "method": "turn/start",
                    "params": {
                        "threadId": self.thread_id,
                        "input": [{"type": "text", "text": prompt}],
                        "approvalPolicy": "never",
                        "sandboxPolicy": {"type": "readOnly", "networkAccess": False},
                    },
                }
            )
            answer = ""
            usage: dict[str, int] = {}
            model_seconds: float | None = None
            deadline = started + self.host.spec.timeout_seconds
            while True:
                event = self._next_event(deadline)
                if event.get("id") == request_id and "error" in event:
                    raise ReasonerUnavailableError("Codex app-server turn/start failed")
                self._observe(event)
                method = event.get("method")
                params = event.get("params")
                if method == "item/completed" and isinstance(params, dict):
                    item = params.get("item")
                    if (
                        isinstance(item, dict)
                        and item.get("type") == "agentMessage"
                        and isinstance(item.get("text"), str)
                    ):
                        answer = item["text"].strip()
                elif method == "thread/tokenUsage/updated" and isinstance(params, dict):
                    token_usage = params.get("tokenUsage")
                    last = token_usage.get("last") if isinstance(token_usage, dict) else None
                    if isinstance(last, dict):
                        usage = {
                            target: value
                            for source, target in (
                                ("inputTokens", "input_tokens"),
                                ("cachedInputTokens", "cached_input_tokens"),
                                ("outputTokens", "output_tokens"),
                            )
                            if isinstance((value := last.get(source)), int)
                        }
                elif method == "turn/completed" and isinstance(params, dict):
                    turn = params.get("turn")
                    status = turn.get("status") if isinstance(turn, dict) else None
                    if status != "completed":
                        raise ReasonerUnavailableError(f"Codex app-server turn ended as {status!r}")
                    duration_ms = turn.get("durationMs") if isinstance(turn, dict) else None
                    if isinstance(duration_ms, int):
                        model_seconds = duration_ms / 1000
                    break
            elapsed = time.monotonic() - started
            self.model_turn_seconds.append(model_seconds)
            if not answer:
                result = HostResult(
                    "",
                    False,
                    elapsed,
                    "missing or empty Codex final message",
                    session_id=self.thread_id,
                    input_tokens=usage.get("input_tokens"),
                    cached_input_tokens=usage.get("cached_input_tokens"),
                    output_tokens=usage.get("output_tokens"),
                )
            else:
                result = HostResult(
                    answer,
                    True,
                    elapsed,
                    session_id=self.thread_id,
                    input_tokens=usage.get("input_tokens"),
                    cached_input_tokens=usage.get("cached_input_tokens"),
                    output_tokens=usage.get("output_tokens"),
                )
        except ReasonerUnavailableError as error:
            self.model_turn_seconds.append(None)
            result = HostResult(
                "",
                False,
                time.monotonic() - started,
                str(error),
                session_id=self.thread_id,
            )
        self.results.append(result)
        return result

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        process = self._process
        if process is not None:
            if process.stdin is not None:
                with suppress(OSError):
                    process.stdin.close()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        self._scratch.cleanup()
