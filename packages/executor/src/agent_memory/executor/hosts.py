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

import dataclasses
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import time

from agent_memory.core import observation

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
CODEX_SANDBOX_TOOLS = "workspace-write"
CODEX_SANDBOX_READONLY = "read-only"
BARE_SYSTEM_PROMPT = "You are a helpful assistant. Answer the user directly and concisely."
PROMPT_PLACEHOLDER = "<<prompt>>"
PROMPT_SEPARATOR = "\n\n"
ERROR_EXCERPT = 400
ANSWER_FILENAME = "answer.txt"
PROMPT_FILENAME = "prompt.txt"


@dataclasses.dataclass(frozen=True)
class HostResult:
    text: str
    ok: bool
    seconds: float
    error: str = ""


@dataclasses.dataclass(frozen=True)
class HostSpec:
    name: str
    binary: str
    model: str = DEFAULT_MODEL
    timeout_seconds: float = 300.0
    attempts: int = 3
    retry_backoff_seconds: float = 5.0
    provider: str = ""
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
            command += ["--tools", ""]
        return command + ["--system-prompt", system_prompt or BARE_SYSTEM_PROMPT]

    def disables_native_memory(self, rendered_command: str) -> bool:
        return CLAUDE_NATIVE_TOOLS in rendered_command


class CodexDialect(Dialect):
    """No system-prompt flag, so it rides in the prompt; and stdout carries the whole session
    transcript, so the final message is read from the file the host writes it to."""

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
        return command + ["--ignore-user-config", "--ignore-rules", "--yolo"]

    def routed_model(self, spec: HostSpec) -> str:
        """Hermes eats one `<provider>/` prefix off the model as routing, so a backend that
        wants a publisher-qualified id — Vertex wants `google/<model>` — needs one added back."""
        return f"{spec.provider}/{spec.model}" if spec.provider else spec.model

    def stdin(self, prompt: str, system_prompt: str) -> str:
        return (system_prompt + PROMPT_SEPARATOR + prompt) if system_prompt else prompt

    def disables_native_memory(self, rendered_command: str) -> bool:
        _, _, tail = rendered_command.partition("-t ")
        toolsets = tail.split(" ")[0] if tail else ""
        return "memory" not in toolsets.split(",")


class MuseCodeDialect(Dialect):
    """Muse's headless transport: JSONL out, prompt file in, sandbox kept on."""

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
            "--prompt-file",
            PROMPT_PLACEHOLDER,
            "--max-model-steps",
            str(max_turns),
            "--workspace",
            str(workspace),
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
        return "--workspace" in rendered_command

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
        self.credentials = VertexCredentials() if spec.name == HOST_HERMES else None

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
        last = HostResult(text="", ok=False, seconds=0.0, error="not attempted")
        for attempt in range(self.spec.attempts):
            last = self._attempt(
                prompt,
                store_root,
                tools_enabled,
                system_prompt,
                max_turns,
                workdir,
                environment or {},
                tool_pattern,
            )
            if last.ok:
                return last
            if attempt + 1 < self.spec.attempts:
                time.sleep(self.spec.retry_backoff_seconds * (attempt + 1))
        return last

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
            answer_file = pathlib.Path(scratch) / ANSWER_FILENAME
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
            command, payload = self.dialect.invocation(
                command, prompt, system_prompt, pathlib.Path(scratch)
            )
            return self._invoke(
                command, payload, self._environment(store_root, environment), workdir, answer_file
            )

    def _invoke(
        self,
        command: list[str],
        payload: str,
        environment: dict[str, str],
        workdir: pathlib.Path | None,
        answer_file: pathlib.Path,
    ) -> HostResult:
        started = time.monotonic()
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
        try:
            completed = subprocess.run(
                command,
                input=payload,
                capture_output=True,
                text=True,
                timeout=self.spec.timeout_seconds,
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
        capture(
            state="completed",
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
        if completed.returncode != 0:
            detail = (completed.stderr.strip() or completed.stdout.strip())[:ERROR_EXCERPT]
            return HostResult("", False, elapsed, detail or "non-zero exit with no output")
        text = self.dialect.answer(completed.stdout, answer_file)
        if self.spec.name in (HOST_CODEX, HOST_MUSE_CODE) and not text:
            label = "Codex" if self.spec.name == HOST_CODEX else "Muse"
            return HostResult("", False, elapsed, f"missing or empty {label} final message")
        return HostResult(text, True, elapsed)

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
