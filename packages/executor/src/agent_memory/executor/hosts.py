"""Headless host drivers. The harness shells out; it never speaks a model API itself.

Each host is a dialect: how it takes a system prompt, how it is told which tools it may use,
and where its final answer comes out. Adding a host is adding a dialect, never a branch in the
driver — the same rule adapters follow (Invariant 8).

One rule binds all of them. A host that ships its own memory layer will use it, silently, and
report success while the store under test stays empty; two memory systems in one run make the
score unattributable. Every dialect switches its host's own memory off, and a test holds each
of them to it.
"""

from __future__ import annotations

import contextlib
import dataclasses
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable

from agent_memory.core import observation
from agent_memory.core.config import MUSE_SETTINGS_ENV_VAR

from . import muse_namespaces
from .credentials import VertexCredentials

HOST_CLAUDE_CODE = "claude-code"
HOST_CODEX = "codex"
HOST_HERMES = "hermes"
HOST_MUSE_CODE = "muse-code"

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
BINARIES = {
    HOST_CLAUDE_CODE: ("claude", DEFAULT_MODEL),
    HOST_CODEX: ("codex", "gpt-5.6-sol"),
    HOST_HERMES: ("hermes", "google/gemini-3.7-flash"),
    HOST_MUSE_CODE: ("muse", ""),
}
MEM_TOOL_PATTERN = "Bash(mem:*)"
CLAUDE_NATIVE_TOOLS = "Write,Edit,NotebookEdit,WebSearch,WebFetch,Task"
HERMES_TOOLSETS = "terminal"
HERMES_WRITE_SERVER_NAME = "agent-memory-write"
HERMES_MANAGE_SERVER_NAME = "agent-memory-manage"
HERMES_NATIVE_MAX_TURNS = 8
HERMES_NATIVE_TOOL_REQUIREMENT = "Hermes native tools require Hermes Agent 0.22.2 or newer"
# Kept for callers that imported the Write-specific name before Manage reused the same runtime.
HERMES_NATIVE_WRITE_REQUIREMENT = HERMES_NATIVE_TOOL_REQUIREMENT
HERMES_DATA_TRAINING_REQUIREMENT = (
    "Hermes contributor models require host_allow_data_training = true"
)
CODEX_SANDBOX_TOOLS = "workspace-write"
CODEX_SANDBOX_READONLY = "read-only"
BARE_SYSTEM_PROMPT = "You are a helpful assistant. Answer the user directly and concisely."
PROMPT_PLACEHOLDER = "<<prompt>>"
PROMPT_SEPARATOR = "\n\n"
ERROR_EXCERPT = 400
ANSWER_FILENAME = "answer.txt"
PROMPT_FILENAME = "prompt.txt"
INSTRUCTIONS_FILENAME = "instructions.md"
CODEX_TOOL_APPROVAL = "approve"
CODEX_DISABLED_FEATURES = (
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
MUSE_TOOLSET_SETTING = "run.toolset"
MUSE_NATIVE_TOOL_REQUIREMENT = "Muse native tools require Muse Code 1.4.4 or newer"
MUSE_RUNTIME_TMPDIR = "/var/tmp"
MUSE_NATIVE_MAX_MODEL_STEPS = 8


@dataclasses.dataclass(frozen=True)
class HostResult:
    text: str
    ok: bool
    seconds: float
    error: str = ""
    usage: HostUsage | None = None
    phases: HostPhases | None = None


@dataclasses.dataclass(frozen=True)
class HostUsage:
    turns: int
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int


@dataclasses.dataclass(frozen=True)
class HostPhases:
    """Observed Codex process phases; together they account for Host wall time."""

    startup_seconds: float
    model_wait_seconds: float
    mcp_seconds: float
    shutdown_seconds: float


@dataclasses.dataclass(frozen=True)
class ToolServer:
    """A stdio MCP server the host starts for one run, and the only tools it may call."""

    name: str
    command: str
    args: tuple[str, ...]
    tools: tuple[str, ...]
    host_analytics_enabled: bool = True


@dataclasses.dataclass(frozen=True)
class HostSpec:
    name: str
    binary: str
    model: str = DEFAULT_MODEL
    timeout_seconds: float = 300.0
    attempts: int = 3
    retry_backoff_seconds: float = 5.0
    provider: str = ""
    allow_data_training: bool = False
    reasoning_effort: str = ""

    def available(self) -> bool:
        return shutil.which(self.binary) is not None

    def version(self) -> str:
        resolved = shutil.which(self.binary)
        if resolved is None:
            return "unavailable"
        try:
            completed = subprocess.run(
                [resolved, "--version"], capture_output=True, text=True, check=False, timeout=10
            )
        except (OSError, subprocess.TimeoutExpired):
            return "unknown"
        output = (completed.stdout.strip() or completed.stderr.strip()).splitlines()
        return output[0] if completed.returncode == 0 and output else "unknown"


class Dialect:
    """How one host is spoken to. Every method is pure, so the shape is testable offline."""

    prompt_on_stdin = True
    supports_tools = False
    tools_by_default = False

    def tool_command(
        self,
        spec: HostSpec,
        *,
        system_prompt: str,
        instructions_file: pathlib.Path,
        server: ToolServer,
        answer_file: pathlib.Path,
    ) -> list[str]:
        raise NotImplementedError

    def command(
        self,
        spec: HostSpec,
        *,
        tools_enabled: bool,
        system_prompt: str,
        max_turns: int,
        store_root: pathlib.Path | None,
        answer_file: pathlib.Path,
        tool_pattern: str = MEM_TOOL_PATTERN,
        workdir: pathlib.Path | None = None,
    ) -> list[str]:
        raise NotImplementedError

    def stdin(self, prompt: str, system_prompt: str) -> str:
        return prompt

    def answer(self, stdout: str, answer_file: pathlib.Path) -> str:
        return stdout.strip()

    def disables_native_memory(self, rendered_command: str) -> bool:
        raise NotImplementedError

    def invocation(
        self,
        command: list[str],
        prompt: str,
        system_prompt: str,
        scratch: pathlib.Path,
    ) -> tuple[list[str], str]:
        payload = self.stdin(prompt, system_prompt)
        if self.prompt_on_stdin:
            return command, payload
        return [payload if part == PROMPT_PLACEHOLDER else part for part in command], ""


class ClaudeCodeDialect(Dialect):
    """Its memory is the Write tool aimed at ~/.claude/projects/<cwd>/memory/."""

    supports_tools = True
    tools_by_default = True

    def tool_command(self, spec, *, system_prompt, instructions_file, server, answer_file):
        configured = {
            "mcpServers": {
                server.name: {"type": "stdio", "command": server.command, "args": list(server.args)}
            }
        }
        allowed = ",".join(f"mcp__{server.name}__{tool}" for tool in server.tools)
        return [
            spec.binary,
            "-p",
            "--model",
            spec.model,
            "--strict-mcp-config",
            "--mcp-config",
            json.dumps(configured),
            "--tools",
            "",
            "--allowedTools",
            allowed,
            "--disallowedTools",
            CLAUDE_NATIVE_TOOLS,
            "--system-prompt-file",
            str(instructions_file),
        ]

    def command(
        self,
        spec,
        *,
        tools_enabled,
        system_prompt,
        max_turns,
        store_root,
        answer_file,
        tool_pattern=MEM_TOOL_PATTERN,
        workdir=None,
    ):
        command = [
            spec.binary,
            "-p",
            "--model",
            spec.model,
            "--max-turns",
            str(max_turns),
            "--disallowedTools",
            CLAUDE_NATIVE_TOOLS,
        ]
        if tools_enabled:
            command += ["--allowedTools", tool_pattern]
        else:
            command += ["--tools", "", "--strict-mcp-config"]
        return command + ["--system-prompt", system_prompt or BARE_SYSTEM_PROMPT]

    def disables_native_memory(self, rendered_command: str) -> bool:
        return CLAUDE_NATIVE_TOOLS in rendered_command


class CodexDialect(Dialect):
    """No system-prompt flag, so it rides in the prompt; and stdout carries the whole session
    transcript, so the final message is read from the file the host writes it to."""

    supports_tools = True
    tools_by_default = True

    def tool_command(self, spec, *, system_prompt, instructions_file, server, answer_file):
        prefix = f"mcp_servers.{server.name}"
        overrides = {
            "model_instructions_file": str(instructions_file),
            f"{prefix}.command": server.command,
            f"{prefix}.args": list(server.args),
            f"{prefix}.required": True,
            f"{prefix}.enabled_tools": list(server.tools),
            f"{prefix}.default_tools_approval_mode": CODEX_TOOL_APPROVAL,
        }
        if not server.host_analytics_enabled:
            # A bounded machine-consumed review has no use for delaying process shutdown on
            # Codex's synchronous analytics flush. This does not alter the agent turn or MCP.
            overrides["analytics.enabled"] = False
        command = [
            spec.binary,
            "exec",
            "--model",
            spec.model,
            "--skip-git-repo-check",
            "--ephemeral",
            "--json",
            "--ignore-user-config",
            "--ignore-rules",
            "--sandbox",
            CODEX_SANDBOX_READONLY,
            "--output-last-message",
            str(answer_file),
        ]
        for key, value in overrides.items():
            command += ["-c", f"{key}={json.dumps(value)}"]
        for feature in CODEX_DISABLED_FEATURES:
            command += ["--disable", feature]
        return command

    def command(
        self,
        spec,
        *,
        tools_enabled,
        system_prompt,
        max_turns,
        store_root,
        answer_file,
        tool_pattern=MEM_TOOL_PATTERN,
        workdir=None,
    ):
        command = [
            spec.binary,
            "exec",
            "--model",
            spec.model,
            "--skip-git-repo-check",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--output-last-message",
            str(answer_file),
        ]
        if tools_enabled:
            command += ["--sandbox", CODEX_SANDBOX_TOOLS]
            if store_root is not None:
                command += ["--add-dir", str(store_root)]
            return command
        return command + ["--sandbox", CODEX_SANDBOX_READONLY]

    def stdin(self, prompt: str, system_prompt: str) -> str:
        return (system_prompt + PROMPT_SEPARATOR + prompt) if system_prompt else prompt

    def answer(self, stdout: str, answer_file: pathlib.Path) -> str:
        if answer_file.exists():
            written = answer_file.read_text(encoding="utf-8").strip()
            if written:
                return written
        return ""

    def disables_native_memory(self, rendered_command: str) -> bool:
        return "--ignore-user-config" in rendered_command


class HermesDialect(Dialect):
    """One-shot mode loads its own memory toolset by default; the toolset list drops it."""

    prompt_on_stdin = False
    supports_tools = True
    tools_by_default = True

    def tool_command(self, spec, *, system_prompt, instructions_file, server, answer_file):
        toolset = self.toolset(server)
        command = [
            spec.binary,
            "chat",
            "--oneshot",
            "--query-file",
            PROMPT_PLACEHOLDER,
            "--model",
            self.routed_model(spec),
            "--toolsets",
            toolset,
            "--max-turns",
            str(HERMES_NATIVE_MAX_TURNS),
            "--ignore-rules",
        ]
        if spec.provider:
            command += ["--provider", spec.provider]
        return command

    @staticmethod
    def toolset(server: ToolServer) -> str:
        """Give Write and Manage distinct names without exposing arbitrary profile servers."""
        if server.name == "memory":
            return HERMES_WRITE_SERVER_NAME
        if server.name == "memory_review":
            return HERMES_MANAGE_SERVER_NAME
        return server.name

    def command(
        self,
        spec,
        *,
        tools_enabled,
        system_prompt,
        max_turns,
        store_root,
        answer_file,
        tool_pattern=MEM_TOOL_PATTERN,
        workdir=None,
    ):
        command = [spec.binary, "-z", PROMPT_PLACEHOLDER, "--model", self.routed_model(spec)]
        if spec.provider:
            command += ["--provider", spec.provider]
        command += ["-t", HERMES_TOOLSETS if tools_enabled else ""]
        return command + ["--ignore-rules", "--yolo"]

    def routed_model(self, spec: HostSpec) -> str:
        """Hermes eats one `<provider>/` prefix off the model as routing, so a backend that
        wants a publisher-qualified id — Vertex wants `google/<model>` — needs one added back."""
        if spec.provider == "gemini":
            return f"{spec.provider}/{spec.model}"
        return spec.model

    def stdin(self, prompt: str, system_prompt: str) -> str:
        return (system_prompt + PROMPT_SEPARATOR + prompt) if system_prompt else prompt

    def invocation(self, command, prompt, system_prompt, scratch):
        prompt_path = scratch / PROMPT_FILENAME
        prompt_path.write_text(self.stdin(prompt, system_prompt), encoding="utf-8")
        return [str(prompt_path) if part == PROMPT_PLACEHOLDER else part for part in command], ""

    def disables_native_memory(self, rendered_command: str) -> bool:
        marker = "--toolsets " if "--toolsets " in rendered_command else "-t "
        _, _, tail = rendered_command.partition(marker)
        toolsets = tail.split(" ")[0] if tail else ""
        return "memory" not in toolsets.split(",")


class MuseCodeDialect(Dialect):
    """Muse's headless transport: JSONL out, prompt file in, sandbox kept on."""

    supports_tools = True
    tools_by_default = True

    def tool_command(self, spec, *, system_prompt, instructions_file, server, answer_file):
        selected = [f"mcp__{server.name}__{tool}" for tool in server.tools]
        command = [
            spec.binary,
            "exec",
            "-c",
            f"{MUSE_TOOLSET_SETTING}={json.dumps(selected)}",
            "--json",
            "--no-foreign-personal-context",
            "--disable-reminders",
            "--no-session-log",
            "--disable-shell",
            "--disable-web-tools",
            "--disable-write",
            "--approval-mode",
            "never",
            "--max-model-steps",
            str(MUSE_NATIVE_MAX_MODEL_STEPS),
            "--prompt-file",
            PROMPT_PLACEHOLDER,
            "--workspace",
            str(answer_file.parent.resolve()),
        ]
        if spec.model:
            command += ["--model", spec.model]
        if spec.reasoning_effort:
            command += ["--reasoning-effort", spec.reasoning_effort]
        return command

    def command(
        self,
        spec,
        *,
        tools_enabled,
        system_prompt,
        max_turns,
        store_root,
        answer_file,
        tool_pattern=MEM_TOOL_PATTERN,
        workdir=None,
    ):
        workspace = self._workspace(tools_enabled, store_root, workdir, answer_file.parent)
        command = [
            spec.binary,
            "exec",
            "--json",
            "--no-foreign-personal-context",
            "--disable-reminders",
            "--prompt-file",
            PROMPT_PLACEHOLDER,
            "--max-model-steps",
            str(max_turns),
            "--workspace",
            str(workspace),
        ]
        if not tools_enabled:
            command += [
                "--disable-shell",
                "--disable-web-tools",
                "--approval-mode",
                "never",
            ]
        if spec.model:
            command += ["--model", spec.model]
        if spec.reasoning_effort:
            command += ["--reasoning-effort", spec.reasoning_effort]
        return command

    def stdin(self, prompt: str, system_prompt: str) -> str:
        return (system_prompt + PROMPT_SEPARATOR + prompt) if system_prompt else prompt

    def invocation(self, command, prompt, system_prompt, scratch):
        prompt_path = scratch / PROMPT_FILENAME
        prompt_path.write_text(self.stdin(prompt, system_prompt), encoding="utf-8")
        return [str(prompt_path) if part == PROMPT_PLACEHOLDER else part for part in command], ""

    def answer(self, stdout: str, answer_file: pathlib.Path) -> str:
        answer = ""
        for line in stdout.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            candidates = [event]
            payload = event.get("payload")
            if isinstance(payload, dict):
                candidates.append(payload)
                nested = payload.get("event")
                if isinstance(nested, dict):
                    candidates.append(nested)
            for candidate in candidates:
                kind = candidate.get("kind")
                text = candidate.get("text")
                if kind in ("run_terminal", "assistant_message", "final_answer") and isinstance(
                    text, str
                ):
                    answer = text.strip()
        return answer

    def disables_native_memory(self, rendered_command: str) -> bool:
        return all(
            flag in rendered_command for flag in ("--workspace", "--no-foreign-personal-context")
        )

    @staticmethod
    def _workspace(tools_enabled, store_root, workdir, scratch):
        if not tools_enabled or store_root is None:
            workspace = (workdir or scratch).resolve()
            MuseCodeDialect._require_no_native_memory(workspace)
            return workspace
        roots = [store_root.resolve(), (workdir or scratch).resolve()]
        common = pathlib.Path(os.path.commonpath([str(path) for path in roots]))
        unsafe = {pathlib.Path("/"), pathlib.Path.home().resolve()}
        if common in unsafe:
            raise ValueError(
                "Muse sandbox needs the experiment store and workdir under one safe workspace"
            )
        MuseCodeDialect._require_no_native_memory(common)
        return common

    @staticmethod
    def _require_no_native_memory(workspace: pathlib.Path) -> None:
        if (workspace / ".agents" / "memory").exists():
            raise ValueError("Muse experiment workspace contains native .agents/memory")


DIALECTS: dict[str, Dialect] = {
    HOST_CLAUDE_CODE: ClaudeCodeDialect(),
    HOST_CODEX: CodexDialect(),
    HOST_HERMES: HermesDialect(),
    HOST_MUSE_CODE: MuseCodeDialect(),
}


class Host:
    def __init__(self, spec: HostSpec):
        self.spec = spec
        self.dialect = DIALECTS.get(spec.name, DIALECTS[HOST_CLAUDE_CODE])
        self.credentials = (
            VertexCredentials()
            if spec.name == HOST_HERMES and spec.provider in ("", "gemini")
            else None
        )

    @property
    def name(self) -> str:
        return self.spec.name

    def run(
        self,
        prompt: str,
        store_root: pathlib.Path | None = None,
        tools_enabled: bool = False,
        system_prompt: str = "",
        max_turns: int = 8,
        workdir: pathlib.Path | None = None,
        environment: dict[str, str] | None = None,
        tool_pattern: str = MEM_TOOL_PATTERN,
    ) -> HostResult:
        return self._retrying(
            lambda: self._attempt(
                prompt,
                store_root,
                tools_enabled,
                system_prompt,
                max_turns,
                workdir,
                environment or {},
                tool_pattern,
            )
        )

    def converse(
        self,
        prompt: str,
        *,
        system_prompt: str,
        server: ToolServer,
        environment: dict[str, str] | None = None,
        timeout_seconds: float | None = None,
    ) -> HostResult:
        """One headless run in which the host's own loop calls only the server's tools."""
        return self._retrying(
            lambda: self._converse_attempt(
                prompt, system_prompt, server, environment or {}, timeout_seconds
            )
        )

    def _retrying(self, attempt: Callable[[], HostResult]) -> HostResult:
        last = HostResult(text="", ok=False, seconds=0.0, error="not attempted")
        for number in range(self.spec.attempts):
            last = attempt()
            if last.ok or last.error in (
                MUSE_NATIVE_TOOL_REQUIREMENT,
                HERMES_NATIVE_TOOL_REQUIREMENT,
            ):
                return last
            if number + 1 < self.spec.attempts:
                time.sleep(self.spec.retry_backoff_seconds * (number + 1))
        return last

    def _converse_attempt(
        self,
        prompt: str,
        system_prompt: str,
        server: ToolServer,
        environment: dict[str, str],
        timeout_seconds: float | None,
    ) -> HostResult:
        with tempfile.TemporaryDirectory() as scratch:
            scratch_path = pathlib.Path(scratch)
            answer_file = scratch_path / ANSWER_FILENAME
            instructions_file = scratch_path / INSTRUCTIONS_FILENAME
            instructions_file.write_text(system_prompt, encoding="utf-8")
            command = self.dialect.tool_command(
                self.spec,
                system_prompt=system_prompt,
                instructions_file=instructions_file,
                server=server,
                answer_file=answer_file,
            )
            settings = None
            if self.spec.name == HOST_HERMES:
                command, prompt = self.dialect.invocation(
                    command, prompt, system_prompt, scratch_path
                )
            elif self.spec.name == HOST_MUSE_CODE:
                environment = self._isolated_muse_environment(environment, scratch_path)
                # Muse 1.4.9 rejects its process-lifetime tool-output root when TMPDIR and the
                # workspace share the /tmp tree. Muse creates and cleans its own unique child.
                environment["TMPDIR"] = MUSE_RUNTIME_TMPDIR
                self._stage_muse_tool_server(environment, server)
                settings = pathlib.Path(environment["XDG_CONFIG_HOME"]) / "muse" / "settings.json"
                command, prompt = self.dialect.invocation(
                    command, prompt, system_prompt, scratch_path
                )

            def invoke() -> HostResult:
                return self._invoke(
                    command,
                    prompt,
                    self._environment(None, environment),
                    scratch_path,
                    answer_file,
                    require_answer=False,
                    timeout_seconds=timeout_seconds,
                )

            if settings is not None:
                with muse_namespaces.for_muse_settings(settings):
                    return invoke()
            if self.spec.name == HOST_HERMES:
                with self._isolated_hermes_environment(
                    environment,
                    server,
                    allow_data_training=self.spec.allow_data_training,
                ) as isolated:
                    environment = isolated
                    return invoke()
            return invoke()

    @staticmethod
    @contextlib.contextmanager
    def _isolated_hermes_environment(
        extra: dict[str, str],
        server: ToolServer | None,
        *,
        allow_data_training: bool = False,
    ):
        """Give Hermes an ephemeral profile that reuses only its installed runtime.

        Hermes scopes dependency environments to the data root containing ``profiles/``.
        A profile below that root therefore keeps the installed CLI usable while isolating
        config, sessions, skills, and native memory.  An unrelated temporary HERMES_HOME would
        instead be treated as a new installation and try to provision dependencies per Write.
        """
        source = {**os.environ, **extra}
        root = Host._hermes_data_root(source)
        profiles = root / "profiles"
        profiles.mkdir(parents=True, exist_ok=True)
        home = pathlib.Path(tempfile.mkdtemp(prefix="agent-memory-", dir=profiles))
        configured: dict[str, object] = {}
        if server is not None:
            toolset = HermesDialect.toolset(server)
            configured["mcp_servers"] = {
                toolset: {
                    "command": server.command,
                    "args": list(server.args),
                    "enabled": True,
                    "tools": {
                        "include": list(server.tools),
                        "resources": False,
                        "prompts": False,
                    },
                }
            }
        if allow_data_training:
            configured["security"] = {"allow_data_training_tiers_noninteractive": True}
        try:
            target = home / "config.yaml"
            target.write_text(
                json.dumps(configured, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            yield {
                **extra,
                "HERMES_HOME": str(home),
                "HERMES_DISABLE_LAZY_INSTALLS": "1",
            }
        finally:
            shutil.rmtree(home, ignore_errors=True)

    @staticmethod
    def _hermes_data_root(environment: dict[str, str]) -> pathlib.Path:
        configured = environment.get("HERMES_HOME", "").strip()
        if configured:
            home = pathlib.Path(os.path.expandvars(configured)).expanduser()
            return home.parent.parent if home.parent.name == "profiles" else home
        suffix = environment.get("HERMES_DATA_DIR_SUFFIX", "")
        if os.name == "nt":
            local = environment.get("LOCALAPPDATA", "").strip()
            base = pathlib.Path(local) if local else pathlib.Path.home() / "AppData" / "Local"
            return base / f"hermes{suffix}"
        user_home = pathlib.Path(environment.get("HOME", str(pathlib.Path.home()))).expanduser()
        return user_home / f".hermes{suffix}"

    def _attempt(
        self,
        prompt: str,
        store_root: pathlib.Path | None,
        tools_enabled: bool,
        system_prompt: str,
        max_turns: int,
        workdir: pathlib.Path | None,
        environment: dict[str, str],
        tool_pattern: str,
    ) -> HostResult:
        with tempfile.TemporaryDirectory() as scratch:
            scratch_path = pathlib.Path(scratch)
            answer_file = scratch_path / ANSWER_FILENAME
            command = self.dialect.command(
                self.spec,
                tools_enabled=tools_enabled,
                system_prompt=system_prompt,
                max_turns=max_turns,
                store_root=store_root,
                answer_file=answer_file,
                tool_pattern=tool_pattern,
                workdir=workdir,
            )
            if self.spec.name == HOST_CODEX and tools_enabled and environment.get(observation.ENV):
                command += ["--add-dir", environment[observation.ENV]]
            command, payload = self.dialect.invocation(command, prompt, system_prompt, scratch_path)
            if self.spec.name == HOST_MUSE_CODE:
                environment = self._isolated_muse_environment(environment, scratch_path)

            def invoke() -> HostResult:
                return self._invoke(
                    command,
                    payload,
                    self._environment(store_root, environment),
                    workdir,
                    answer_file,
                )

            if self.spec.name == HOST_HERMES:
                with self._isolated_hermes_environment(
                    environment,
                    None,
                    allow_data_training=self.spec.allow_data_training,
                ) as isolated:
                    environment = isolated
                    return invoke()
            return invoke()

    @staticmethod
    def _isolated_muse_environment(extra: dict[str, str], scratch: pathlib.Path) -> dict[str, str]:
        """Keep personal Muse context out while reusing credential and provider routing."""
        source = {**os.environ, **extra}
        source_home = pathlib.Path(source.get("HOME", "~")).expanduser()
        source_config = pathlib.Path(source.get("XDG_CONFIG_HOME") or source_home / ".config")
        configured_settings = source.get(MUSE_SETTINGS_ENV_VAR, "").strip()
        source_settings = (
            pathlib.Path(configured_settings).expanduser()
            if configured_settings
            else source_config / "muse" / "settings.json"
        )
        auth_path = pathlib.Path(
            source.get("MUSE_AUTH_PATH") or source_settings.with_name("auth.json")
        ).expanduser()
        home = scratch / "muse-home"
        config = scratch / "muse-config"
        data = scratch / "muse-data"
        for path in (home, config, data):
            path.mkdir()
        Host._stage_muse_routing(source_settings, config)
        staged_auth = Host._stage_muse_auth(auth_path, config)
        return {
            **extra,
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(config),
            "XDG_DATA_HOME": str(data),
            "MUSE_AUTH_PATH": str(staged_auth),
            "MUSE_NO_AUTO_UPDATE": "1",
        }

    @staticmethod
    def _stage_muse_auth(source: pathlib.Path, config_home: pathlib.Path) -> pathlib.Path:
        if not source.is_file():
            return source
        target = config_home / "muse" / "auth.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        target.chmod(0o600)
        return target

    @staticmethod
    def _stage_muse_routing(source: pathlib.Path, config_home: pathlib.Path) -> None:
        """Copy only deterministic transport fields; hooks and personal settings stay out."""
        try:
            parsed = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(parsed, dict):
            return
        allowed = ("schema_version", "provider", "model", "endpoint_transport")
        routing = {key: parsed[key] for key in allowed if key in parsed}
        if not routing:
            return
        target = config_home / "muse" / "settings.json"
        target.parent.mkdir(parents=True)
        target.write_text(json.dumps(routing, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    @staticmethod
    def _stage_muse_tool_server(environment: dict[str, str], server: ToolServer) -> None:
        config_home = pathlib.Path(environment["XDG_CONFIG_HOME"])
        target = config_home / "muse" / "settings.json"
        try:
            settings = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            settings = {}
        if not isinstance(settings, dict):
            settings = {}
        settings["schema_version"] = 1
        settings["mcp_servers"] = {
            server.name: {
                "transport": "stdio",
                "command": server.command,
                "args": list(server.args),
                "enabled": True,
                "mode": "required",
            }
        }
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(settings, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _invoke(
        self,
        command: list[str],
        payload: str,
        environment: dict[str, str],
        workdir: pathlib.Path | None,
        answer_file: pathlib.Path,
        require_answer: bool = True,
        timeout_seconds: float | None = None,
    ) -> HostResult:
        started = time.monotonic()
        command = [shutil.which(command[0]) or command[0], *command[1:]]
        evidence = environment.get(observation.ENV)
        attempt_id = str(time.time_ns())

        def capture(**data):
            if evidence:
                observation.emit(
                    "host_attempt",
                    directory=evidence,
                    channel="host",
                    attempt_id=attempt_id,
                    host=self.spec.name,
                    **data,
                )

        capture(state="started")
        if evidence:
            environment = {**environment, observation.ATTEMPT_ENV: attempt_id}
        phase_trace = None
        try:
            timeout = timeout_seconds or self.spec.timeout_seconds
            if self.spec.name == HOST_CODEX and "--json" in command:
                completed, phase_trace = _run_codex_jsonl(
                    command,
                    payload,
                    timeout=timeout,
                    environment=environment,
                    workdir=workdir,
                    started=started,
                )
            else:
                completed = subprocess.run(
                    command,
                    input=payload,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=timeout,
                    env=environment,
                    cwd=str(workdir) if workdir else None,
                    check=False,
                )
        except subprocess.TimeoutExpired as error:

            def decoded(value):
                return value.decode(errors="replace") if isinstance(value, bytes) else value or ""

            capture(state="timeout", stdout=decoded(error.stdout), stderr=decoded(error.stderr))
            return HostResult("", False, time.monotonic() - started, "timeout")
        except OSError as error:
            capture(state="error", error_type=type(error).__name__)
            return HostResult("", False, time.monotonic() - started, str(error))
        elapsed = time.monotonic() - started
        phases = phase_trace.phases(started + elapsed) if phase_trace else None
        capture(
            state="completed",
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
        if completed.returncode != 0:
            detail = (completed.stderr.strip() or completed.stdout.strip())[:ERROR_EXCERPT]
            if (
                self.spec.name == HOST_HERMES
                and "--toolsets" in command
                and (
                    "unrecognized arguments" in detail
                    or "unknown option" in detail
                    or "invalid choice" in detail
                )
            ):
                detail = HERMES_NATIVE_TOOL_REQUIREMENT
            if (
                self.spec.name == HOST_MUSE_CODE
                and MUSE_TOOLSET_SETTING in " ".join(command)
                and ("unexpected argument '-c'" in detail or "unknown option" in detail)
            ):
                detail = MUSE_NATIVE_TOOL_REQUIREMENT
            return HostResult("", False, elapsed, detail or "non-zero exit with no output")
        text = self.dialect.answer(completed.stdout, answer_file)
        if require_answer and self.spec.name in (HOST_CODEX, HOST_MUSE_CODE) and not text:
            label = "Codex" if self.spec.name == HOST_CODEX else "Muse"
            return HostResult("", False, elapsed, f"missing or empty {label} final message")
        return HostResult(
            text,
            True,
            elapsed,
            usage=_host_usage(completed.stdout),
            phases=phases,
        )

    def _environment(
        self, store_root: pathlib.Path | None, extra: dict[str, str]
    ) -> dict[str, str]:
        """The memory system's own variables win; the store root is the native default."""
        environment = dict(os.environ)
        if store_root is not None:
            environment["AGENT_MEMORY_STORE"] = str(store_root)
        environment.update(extra)
        for binary in (self.spec.binary, "mem"):
            found = shutil.which(binary)
            if found:
                environment["PATH"] = f"{pathlib.Path(found).parent}:{environment.get('PATH', '')}"
        if self.credentials is not None:
            environment.update(self.credentials.environment())
        return environment


def _host_usage(stdout: str) -> HostUsage | None:
    turns = 0
    totals = {
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
    }
    found = False
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict) or event.get("type") != "turn.completed":
            continue
        turns += 1
        usage = event.get("usage")
        if not isinstance(usage, dict):
            continue
        found = True
        for key in totals:
            value = usage.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                totals[key] += value
    if not found:
        return None
    return HostUsage(turns=turns, **totals)


class _CodexTrace:
    """Timestamp lifecycle JSONL as it arrives; Codex events carry no wall-clock field."""

    def __init__(self, started: float):
        self.started = started
        self.first_event: float | None = None
        self.turn_completed: float | None = None
        self.mcp_started: dict[str, float] = {}
        self.mcp_seconds = 0.0

    def observe(self, line: str, at: float) -> None:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return
        if not isinstance(event, dict):
            return
        if self.first_event is None:
            self.first_event = at
        event_type = event.get("type")
        if event_type == "turn.completed":
            self.turn_completed = at
        if event_type not in ("item.started", "item.completed"):
            return
        item = event.get("item")
        if not isinstance(item, dict) or item.get("type") != "mcp_tool_call":
            return
        item_id = item.get("id")
        if not isinstance(item_id, str):
            return
        if event_type == "item.started":
            self.mcp_started[item_id] = at
        else:
            begun = self.mcp_started.pop(item_id, None)
            if begun is not None:
                self.mcp_seconds += max(0.0, at - begun)

    def phases(self, finished: float) -> HostPhases | None:
        if self.first_event is None or self.turn_completed is None:
            return None
        startup = max(0.0, self.first_event - self.started)
        shutdown = max(0.0, finished - self.turn_completed)
        elapsed = max(0.0, finished - self.started)
        model_wait = max(0.0, elapsed - startup - self.mcp_seconds - shutdown)
        return HostPhases(startup, model_wait, self.mcp_seconds, shutdown)


def _run_codex_jsonl(
    command: list[str],
    payload: str,
    *,
    timeout: float,
    environment: dict[str, str],
    workdir: pathlib.Path | None,
    started: float,
) -> tuple[subprocess.CompletedProcess[str], _CodexTrace]:
    """Capture Codex JSONL receive times without exposing or persisting model content."""
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=environment,
        cwd=str(workdir) if workdir else None,
    )
    stdout: list[str] = []
    stderr: list[str] = []
    trace = _CodexTrace(started)

    def read(stream, sink: list[str], observe: bool = False) -> None:
        for line in iter(stream.readline, ""):
            sink.append(line)
            if observe:
                trace.observe(line, time.monotonic())
        stream.close()

    assert process.stdout is not None and process.stderr is not None and process.stdin is not None
    out_thread = threading.Thread(target=read, args=(process.stdout, stdout, True), daemon=True)
    err_thread = threading.Thread(target=read, args=(process.stderr, stderr), daemon=True)
    out_thread.start()
    err_thread.start()
    try:
        process.stdin.write(payload)
        process.stdin.close()
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired as error:
        process.kill()
        process.wait()
        out_thread.join()
        err_thread.join()
        raise subprocess.TimeoutExpired(
            command, timeout, output="".join(stdout), stderr="".join(stderr)
        ) from error
    out_thread.join()
    err_thread.join()
    return (
        subprocess.CompletedProcess(command, process.returncode, "".join(stdout), "".join(stderr)),
        trace,
    )
