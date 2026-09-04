"""The replay driver: live through the sessions, then sit the exam in a fresh session.

The isolation gate is the validity condition of the whole experiment — the exam prompt is
built from the question alone, so a score can only come from what reached the memory store.
"""

from __future__ import annotations

import concurrent.futures
import dataclasses
import pathlib
import time

from agent_memory.core.config import Config
from agent_memory.core.distill import Ask
from agent_memory.executor import distiller
from agent_memory.executor.hosts import Host

from . import exam as exam_module
from . import framing
from .arms import MODE_COLD, MODE_NONE, Arm
from .dataset import Episode, Session
from .judge import Judge
from .metrics import STATUS_FAILED, STATUS_OK, RunRecord
from .systems import MemorySystem, NativeSystem

SESSION_SEPARATOR = "\n\n"
EXPERIENCE_WORKERS = 4
EXAM_MAX_TURNS = 20


@dataclasses.dataclass(frozen=True)
class ExperiencePhase:
    calls: int
    seconds: float
    blocking_seconds: float
    failures: int


class Driver:
    def __init__(
        self,
        host: Host,
        judge: Judge,
        workspace: pathlib.Path,
        sessions_per_call: int,
        run_id: str,
        episode_fingerprint: str,
        experience_workers: int = EXPERIENCE_WORKERS,
        exam_max_turns: int = EXAM_MAX_TURNS,
        config: Config | None = None,
        reuse_stores: pathlib.Path | None = None,
        exam_mode: str = exam_module.MODE_AGENTIC,
        manage: str = "",
        system: MemorySystem | None = None,
        ask: Ask | None = None,
    ):
        self._host = host
        self._judge = judge
        self._workspace = workspace
        self._batch = sessions_per_call
        self._run_id = run_id
        self._episode_fingerprint = episode_fingerprint
        self._experience_workers = experience_workers
        self._exam_max_turns = exam_max_turns
        self._reuse_stores = reuse_stores
        self._exam_mode = exam_mode
        self._manage = manage
        self._system = system or NativeSystem(config)
        self._ask = ask or distiller.distiller((config or Config.default()).executor)
        if exam_mode == exam_module.MODE_FIXED and not self._system.supports_fixed_exam:
            raise ValueError(
                f"the fixed exam needs a harness-side context builder, "
                f"which {self._system.name} does not have"
            )

    def run(self, episode: Episode, arm: Arm) -> RunRecord:
        root = self._root_for(episode, arm)
        if arm.memory:
            self._system.prepare(root, fresh=self._reuse_stores is None)
        workdir = self._workdir_for(episode, arm)
        phase = (
            ExperiencePhase(calls=0, seconds=0.0, blocking_seconds=0.0, failures=0)
            if self._reuse_stores
            else self._experience(root, episode, arm, workdir)
        )
        fixed = self._exam_mode == exam_module.MODE_FIXED and arm.memory
        if fixed:
            exam_prompt = framing.fixed_exam(episode, exam_module.CONTEXT_PLACEHOLDER)
        else:
            preamble = self._system.exam_preamble() if arm.memory else ""
            exam_prompt = framing.exam(episode, preamble)
        self._assert_isolated(exam_prompt, episode)
        if fixed:
            exam_prompt = exam_module.fill_context(
                exam_prompt, self._system.context(root, episode.question)
            )
        elif arm.memory:
            exam_prompt = framing.with_injected(exam_prompt, self._system.injection(root))

        answer = self._host.run(
            exam_prompt,
            store_root=root if arm.memory else None,
            tools_enabled=arm.memory and not fixed,
            system_prompt=self._exam_system_prompt(arm.memory, fixed),
            max_turns=self._exam_max_turns,
            workdir=workdir,
            environment=self._system.environment(root) if arm.memory else None,
            tool_pattern=self._system.tool_pattern,
        )
        if arm.memory:
            self._system.release(root)
        verdict = self._judge.grade(episode.question, episode.answer, answer.text)
        status = STATUS_OK if answer.ok and verdict.ok else STATUS_FAILED
        return RunRecord(
            run_id=self._run_id,
            arm=arm.name,
            host=self._host.name,
            episode_id=episode.id,
            question_type=episode.question_type,
            status=status,
            correct=bool(verdict.correct and status == STATUS_OK),
            answer=answer.text[:ANSWER_EXCERPT],
            expected=episode.answer[:ANSWER_EXCERPT],
            memories_written=self._system.record_count(root) if arm.memory else 0,
            experience_calls=phase.calls,
            experience_seconds=round(phase.seconds, SECONDS_PRECISION),
            blocking_seconds=round(phase.blocking_seconds, SECONDS_PRECISION),
            exam_seconds=round(answer.seconds, SECONDS_PRECISION),
            judge_seconds=round(verdict.seconds, SECONDS_PRECISION),
            recall_fingerprint=self._system.fingerprint(),
            episode_fingerprint=self._episode_fingerprint,
            error=answer.error,
            manage=self._manage,
            system=self._system.name,
        )

    def _exam_system_prompt(self, with_memory: bool, fixed: bool) -> str:
        if fixed or not with_memory:
            return ""
        return self._system.exam_system_prompt()

    def _root_for(self, episode: Episode, arm: Arm) -> pathlib.Path:
        """A read-side experiment varies R over a fixed W, so it replays the same stores
        rather than rebuilding them — cheaper, and the write side is then provably identical."""
        return (self._reuse_stores or self._workspace) / arm.name / episode.id

    def _workdir_for(self, episode: Episode, arm: Arm) -> pathlib.Path:
        """A clean room per run, and a sibling of the store rather than a child of it:
        the host must not be standing inside the thing being measured."""
        workdir = self._workspace.parent / WORKDIR_NAME / arm.name / episode.id
        workdir.mkdir(parents=True, exist_ok=True)
        return workdir

    def _experience(
        self, root: pathlib.Path, episode: Episode, arm: Arm, workdir: pathlib.Path
    ) -> ExperiencePhase:
        if arm.mode == MODE_NONE:
            return ExperiencePhase(calls=0, seconds=0.0, blocking_seconds=0.0, failures=0)

        batches = list(_batched(list(episode.sessions), self._batch))
        if arm.mode == MODE_COLD:
            return self._cold(root, episode, batches)
        for index, batch in enumerate(batches):
            self._system.archive(root, f"{episode.id}-{index}", _render(batch))

        instructions = [
            framing.experience(
                arm.mode, _render(batch), self._system.record_hint(), self._system.discipline()
            )
            for batch in batches
        ]
        workers = min(self._experience_workers, len(instructions)) or 1
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(
                pool.map(
                    lambda prompt: self._host.run(
                        prompt,
                        store_root=root,
                        tools_enabled=True,
                        system_prompt=self._system.experience_system_prompt(),
                        max_turns=WRITE_MAX_TURNS,
                        workdir=workdir,
                        environment=self._system.environment(root),
                        tool_pattern=self._system.tool_pattern,
                    ),
                    instructions,
                )
            )
        self._system.release(root)
        seconds = sum(result.seconds for result in results)
        return ExperiencePhase(
            calls=len(results),
            seconds=seconds,
            blocking_seconds=seconds if arm.blocking else 0.0,
            failures=len([result for result in results if not result.ok]),
        )

    def _cold(self, root: pathlib.Path, episode: Episode, batches: list) -> ExperiencePhase:
        """W3: the archive is the input and the library's executor is the writer; the host
        is never asked."""
        started = time.monotonic()
        failures = 0
        for index, batch in enumerate(batches):
            try:
                self._system.distill(root, f"{episode.id}-{index}", _render(batch), self._ask)
            except Exception:
                failures += 1
        self._system.release(root)
        return ExperiencePhase(
            calls=len(batches),
            seconds=time.monotonic() - started,
            blocking_seconds=0.0,
            failures=failures,
        )

    def _assert_isolated(self, prompt: str, episode: Episode) -> None:
        """Checked on the harness-built shell, before anything the store returns is placed in
        it. What the store returns came back through retrieval, which is the read track under
        test; what the harness writes must never carry the transcript."""
        for session in episode.sessions:
            for turn in session.turns:
                content = turn.content.strip()
                if len(content) < ISOLATION_MIN_CHARS:
                    continue
                if content[:ISOLATION_EXCERPT] in prompt:
                    raise IsolationBreach(f"{episode.id}: exam prompt carries session content")


class IsolationBreach(Exception):
    """The exam saw the experience. Any score after this is meaningless."""


def _render(sessions: list[Session]) -> str:
    return SESSION_SEPARATOR.join(session.render() for session in sessions)


def _batched(items: list, size: int):
    for start in range(0, len(items), size):
        yield items[start : start + size]


ANSWER_EXCERPT = 600
WORKDIR_NAME = "cwd"
WRITE_MAX_TURNS = 30
ISOLATION_EXCERPT = 60
ISOLATION_MIN_CHARS = 24
SECONDS_PRECISION = 2
