"""Headless host drivers. The harness shells out; it never speaks a model API itself."""

from __future__ import annotations

import dataclasses
import os
import pathlib
import subprocess
import time

HOST_CLAUDE_CODE = "claude-code"
HOST_CODEX = "codex"
DEFAULT_MODEL = "claude-haiku-4-5-20251001"
MEM_TOOL_PATTERN = "Bash(mem:*)"


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
    attempts: int = 2

    def available(self) -> bool:
        return _which(self.binary) is not None


class Host:
    def __init__(self, spec: HostSpec):
        self.spec = spec

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
    ) -> HostResult:
        command = self._command(tools_enabled, system_prompt, max_turns)
        environment = self._environment(store_root)
        last = HostResult(text="", ok=False, seconds=0.0, error="not attempted")
        for _ in range(self.spec.attempts):
            last = self._invoke(command, prompt, environment)
            if last.ok:
                return last
        return last

    def _invoke(self, command: list[str], prompt: str, environment: dict[str, str]) -> HostResult:
        started = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=self.spec.timeout_seconds,
                env=environment,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return HostResult("", False, time.monotonic() - started, "timeout")
        except OSError as error:
            return HostResult("", False, time.monotonic() - started, str(error))
        elapsed = time.monotonic() - started
        if completed.returncode != 0:
            return HostResult("", False, elapsed, completed.stderr.strip()[:ERROR_EXCERPT])
        return HostResult(completed.stdout.strip(), True, elapsed)

    def _command(self, tools_enabled: bool, system_prompt: str, max_turns: int) -> list[str]:
        if self.spec.name == HOST_CLAUDE_CODE:
            command = [self.spec.binary, "-p", "--model", self.spec.model,
                       "--max-turns", str(max_turns)]
            command += ["--allowedTools", MEM_TOOL_PATTERN] if tools_enabled else []
            command += ["--append-system-prompt", system_prompt] if system_prompt else []
            return command
        command = [self.spec.binary, "exec", "--model", self.spec.model, "--skip-git-repo-check"]
        return command + (["--full-auto"] if tools_enabled else ["--sandbox", "read-only"])

    def _environment(self, store_root: pathlib.Path | None) -> dict[str, str]:
        environment = dict(os.environ)
        if store_root is not None:
            environment["AGENT_MEMORY_STORE"] = str(store_root)
        binary_dir = _which(self.spec.binary)
        mem_dir = _which("mem")
        for extra in (binary_dir, mem_dir):
            if extra:
                environment["PATH"] = f"{extra}:{environment.get('PATH', '')}"
        return environment


def _which(binary: str) -> str | None:
    import shutil

    found = shutil.which(binary)
    return str(pathlib.Path(found).parent) if found else None


ERROR_EXCERPT = 400
