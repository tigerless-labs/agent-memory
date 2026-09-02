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
import os
import pathlib
import shutil
import subprocess
import tempfile
import time

HOST_CLAUDE_CODE = "claude-code"
HOST_CODEX = "codex"
HOST_HERMES = "hermes"

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
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

    def available(self) -> bool:
        return shutil.which(self.binary) is not None


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
    ) -> list[str]:
        raise NotImplementedError

    def stdin(self, prompt: str, system_prompt: str) -> str:
        return prompt

    def answer(self, stdout: str, answer_file: pathlib.Path) -> str:
        return stdout.strip()

    def disables_native_memory(self, rendered_command: str) -> bool:
        raise NotImplementedError


class ClaudeCodeDialect(Dialect):
    """Its memory is the Write tool aimed at ~/.claude/projects/<cwd>/memory/."""

    def command(self, spec, *, tools_enabled, system_prompt, max_turns, store_root, answer_file):
        command = [
            spec.binary, "-p",
            "--model", spec.model,
            "--max-turns", str(max_turns),
            "--disallowedTools", CLAUDE_NATIVE_TOOLS,
        ]
        if tools_enabled:
            command += ["--allowedTools", MEM_TOOL_PATTERN]
        return command + ["--system-prompt", system_prompt or BARE_SYSTEM_PROMPT]

    def disables_native_memory(self, rendered_command: str) -> bool:
        return CLAUDE_NATIVE_TOOLS in rendered_command


class CodexDialect(Dialect):
    """No system-prompt flag, so it rides in the prompt; and stdout carries the whole session
    transcript, so the final message is read from the file the host writes it to."""

    def command(self, spec, *, tools_enabled, system_prompt, max_turns, store_root, answer_file):
        command = [
            spec.binary, "exec",
            "--model", spec.model,
            "--skip-git-repo-check",
            "--ignore-user-config",
            "--ignore-rules",
            "--output-last-message", str(answer_file),
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
        return stdout.strip()

    def disables_native_memory(self, rendered_command: str) -> bool:
        return "--ignore-user-config" in rendered_command


class HermesDialect(Dialect):
    """One-shot mode loads its own memory toolset by default; the toolset list drops it."""

    prompt_on_stdin = False

    def command(self, spec, *, tools_enabled, system_prompt, max_turns, store_root, answer_file):
        command = [spec.binary, "-z", PROMPT_PLACEHOLDER, "--model", spec.model]
        if spec.provider:
            command += ["--provider", spec.provider]
        command += ["-t", HERMES_TOOLSETS if tools_enabled else ""]
        return command + ["--ignore-user-config", "--ignore-rules", "--yolo"]

    def stdin(self, prompt: str, system_prompt: str) -> str:
        return (system_prompt + PROMPT_SEPARATOR + prompt) if system_prompt else prompt

    def disables_native_memory(self, rendered_command: str) -> bool:
        _, _, tail = rendered_command.partition("-t ")
        toolsets = tail.split(" ")[0] if tail else ""
        return "memory" not in toolsets.split(",")


DIALECTS: dict[str, Dialect] = {
    HOST_CLAUDE_CODE: ClaudeCodeDialect(),
    HOST_CODEX: CodexDialect(),
    HOST_HERMES: HermesDialect(),
}


class Host:
    def __init__(self, spec: HostSpec):
        self.spec = spec
        self.dialect = DIALECTS.get(spec.name, DIALECTS[HOST_CLAUDE_CODE])

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
    ) -> HostResult:
        last = HostResult(text="", ok=False, seconds=0.0, error="not attempted")
        for attempt in range(self.spec.attempts):
            last = self._attempt(
                prompt, store_root, tools_enabled, system_prompt, max_turns, workdir
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
            )
            payload = self.dialect.stdin(prompt, system_prompt)
            if not self.dialect.prompt_on_stdin:
                command = [payload if part == PROMPT_PLACEHOLDER else part for part in command]
                payload = ""
            return self._invoke(
                command, payload, self._environment(store_root), workdir, answer_file
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
        except subprocess.TimeoutExpired:
            return HostResult("", False, time.monotonic() - started, "timeout")
        except OSError as error:
            return HostResult("", False, time.monotonic() - started, str(error))
        elapsed = time.monotonic() - started
        if completed.returncode != 0:
            detail = (completed.stderr.strip() or completed.stdout.strip())[:ERROR_EXCERPT]
            return HostResult("", False, elapsed, detail or "non-zero exit with no output")
        return HostResult(self.dialect.answer(completed.stdout, answer_file), True, elapsed)

    def _environment(self, store_root: pathlib.Path | None) -> dict[str, str]:
        environment = dict(os.environ)
        if store_root is not None:
            environment["AGENT_MEMORY_STORE"] = str(store_root)
        for binary in (self.spec.binary, "mem"):
            found = shutil.which(binary)
            if found:
                environment["PATH"] = f"{pathlib.Path(found).parent}:{environment.get('PATH', '')}"
        return environment
