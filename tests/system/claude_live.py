"""Gating, recording and evidence shared by the authenticated Claude Code suites."""

from __future__ import annotations

import contextlib
import dataclasses
import json
import os
import pathlib
import shutil
import subprocess
import time

import pytest
from agent_memory.executor.hosts import BINARIES, DEFAULT_MODEL, HOST_CLAUDE_CODE, HostResult
from agent_memory.executor.reasoners import CLAUDE_BUNDLED_ENV, ToolHostReasoner

LIVE_ENV = "AGENT_MEMORY_LIVE_CLAUDE_NATIVE"
MODEL_ENV = "AGENT_MEMORY_LIVE_CLAUDE_MODEL"
EVIDENCE_ENV = "AGENT_MEMORY_LIVE_EVIDENCE"
API_KEY_ENV = "ANTHROPIC_API_KEY"
EVIDENCE_FILENAME = "claude-native.jsonl"
AUTH_TIMEOUT_SECONDS = 20


def model() -> str:
    return os.environ.get(MODEL_ENV) or DEFAULT_MODEL


def binary() -> str | None:
    return shutil.which(BINARIES[HOST_CLAUDE_CODE][0]) or os.environ.get(CLAUDE_BUNDLED_ENV)


def _authenticated(found: str) -> bool:
    if os.environ.get(API_KEY_ENV):
        return True
    try:
        completed = subprocess.run(
            [found, "auth", "status"],
            capture_output=True,
            text=True,
            check=False,
            timeout=AUTH_TIMEOUT_SECONDS,
        )
        return bool(json.loads(completed.stdout).get("loggedIn"))
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, AttributeError):
        return False


def _skip_reason() -> str:
    if os.environ.get(LIVE_ENV) != "1":
        return f"set {LIVE_ENV}=1 for authenticated Claude Code coverage"
    found = binary()
    if found is None:
        return "the claude executable is not installed"
    if not _authenticated(found):
        return "Claude Code is not authenticated"
    return ""


SKIP_REASON = _skip_reason()
requires_live_claude = pytest.mark.skipif(bool(SKIP_REASON), reason=SKIP_REASON or "live")


class RecordingHost:
    """Delegates to the real Host and keeps every process result for the evidence record."""

    def __init__(self, host):
        self.host = host
        self.results: list[HostResult] = []

    @property
    def name(self) -> str:
        return self.host.name

    @property
    def spec(self):
        return self.host.spec

    def converse(self, *args, **kwargs) -> HostResult:
        result = self.host.converse(*args, **kwargs)
        self.results.append(result)
        return result


class Recording:
    """A real Claude tool reasoner whose toolkit record and process results stay inspectable."""

    def __init__(self, delegate: ToolHostReasoner, instruction_suffix: str = ""):
        self.host = RecordingHost(delegate.host)
        self.delegate = dataclasses.replace(delegate, host=self.host)
        self.instruction_suffix = instruction_suffix
        self.record: dict[str, object] = {}
        self.seconds = 0.0

    def __call__(self, prompt: str) -> str:
        return self.delegate(prompt)

    def converse(self, instructions, material, toolkit) -> None:
        self._timed(self.delegate.converse, instructions, material, toolkit)

    def review_converse(self, instructions, material, toolkit):
        return self._timed(self.delegate.review_converse, instructions, material, toolkit)

    def _timed(self, run, instructions, material, toolkit):
        started = time.monotonic()
        try:
            return run(instructions + self.instruction_suffix, material, toolkit)
        finally:
            self.seconds = time.monotonic() - started
            self.record = toolkit.record()

    def tool_names(self) -> list[str]:
        return [str(call["name"]) for call in self.record.get("calls", [])]


@contextlib.contextmanager
def case(name: str, intent: str):
    """Print one evidence line per case, and append it to the evidence file when one is named."""
    entry: dict[str, object] = {"case": name, "intent": intent, "model": model()}
    started = time.monotonic()
    try:
        yield entry
        entry["status"] = "passed"
    except BaseException as error:
        entry["status"] = "failed"
        entry["failure"] = f"{type(error).__name__}: {str(error)[:600]}"
        raise
    finally:
        entry["case_seconds"] = round(time.monotonic() - started, 3)
        found = binary()
        entry["cli"] = _version(found) if found else "unavailable"
        line = json.dumps(entry, sort_keys=True, default=str)
        print(line)
        directory = os.environ.get(EVIDENCE_ENV)
        if directory:
            target = pathlib.Path(directory)
            target.mkdir(parents=True, exist_ok=True)
            with (target / EVIDENCE_FILENAME).open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")


def describe(recording: Recording) -> dict[str, object]:
    usage = [dataclasses.asdict(result.usage) for result in recording.host.results if result.usage]
    return {
        "seconds": round(recording.seconds, 3),
        "host_processes": len(recording.host.results),
        "host_ok": [result.ok for result in recording.host.results],
        "final_text": [result.text[:300] for result in recording.host.results],
        "usage": usage,
        "tool_calls": [
            {
                "name": call["name"],
                "arguments": call["arguments"],
                "is_error": call["is_error"],
                "reply": str(call["text"])[:300],
            }
            for call in recording.record.get("calls", [])
        ],
        "submission": recording.record.get("submission"),
    }


def _version(found: str) -> str:
    try:
        completed = subprocess.run(
            [found, "--version"], capture_output=True, text=True, check=False, timeout=10
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    return completed.stdout.strip() or "unknown"
