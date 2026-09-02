"""The replay driver: live through the sessions, then sit the exam in a fresh session.

The isolation gate is the validity condition of the whole experiment — the exam prompt is
built from the question alone, so a score can only come from what reached the memory store.
"""

from __future__ import annotations

import concurrent.futures
import dataclasses
import pathlib

from agent_memory.core import injection, prompts
from agent_memory.core.config import Config
from agent_memory.core.store import Store

from . import exam as exam_module
from . import framing
from .arms import MODE_NONE, Arm
from .dataset import Episode, Session
from .hosts import Host
from .judge import Judge
from .metrics import STATUS_FAILED, STATUS_OK, RunRecord

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
    ):
        self._host = host
        self._judge = judge
        self._workspace = workspace
        self._batch = sessions_per_call
        self._run_id = run_id
        self._episode_fingerprint = episode_fingerprint
        self._experience_workers = experience_workers
        self._exam_max_turns = exam_max_turns
        self._config = config
        self._reuse_stores = reuse_stores
        self._exam_mode = exam_mode

    def run(self, episode: Episode, arm: Arm) -> RunRecord:
        store = self._store_for(episode, arm)
        workdir = self._workdir_for(episode, arm)
        phase = (
            ExperiencePhase(calls=0, seconds=0.0, blocking_seconds=0.0, failures=0)
            if self._reuse_stores
            else self._experience(store, episode, arm, workdir)
        )
        fixed = self._exam_mode == exam_module.MODE_FIXED and arm.memory
        if fixed:
            context = exam_module.build_context(
                store, episode.question, store.config.recall.fixed_exam_full_text_entries
            )
            exam_prompt = framing.fixed_exam(episode, context.text)
        else:
            exam_prompt = framing.exam(episode, with_memory=arm.memory, config=store.config)
        self._assert_isolated(exam_prompt, episode)
        if arm.memory and not fixed:
            exam_prompt = framing.with_injected_index(exam_prompt, injection.payload(store))

        answer = self._host.run(
            exam_prompt,
            store_root=store.root if arm.memory else None,
            tools_enabled=arm.memory and not fixed,
            system_prompt="" if fixed else (prompts.MEMORY_KEEPER if arm.memory else ""),
            max_turns=self._exam_max_turns,
            workdir=workdir,
        )
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
            memories_written=len(store.records()) if arm.memory else 0,
            experience_calls=phase.calls,
            experience_seconds=round(phase.seconds, SECONDS_PRECISION),
            blocking_seconds=round(phase.blocking_seconds, SECONDS_PRECISION),
            exam_seconds=round(answer.seconds, SECONDS_PRECISION),
            judge_seconds=round(verdict.seconds, SECONDS_PRECISION),
            recall_fingerprint=store.config.recall_fingerprint(),
            episode_fingerprint=self._episode_fingerprint,
            error=answer.error,
        )

    def _store_for(self, episode: Episode, arm: Arm) -> Store:
        """A read-side experiment varies R over a fixed W, so it replays the same stores
        rather than rebuilding them — cheaper, and the write side is then provably identical."""
        root = (self._reuse_stores or self._workspace) / arm.name / episode.id
        config = dataclasses.replace(self._config) if self._config else None
        store = Store(root, config=config, agent=f"harness-{arm.name}")
        if self._reuse_stores is None:
            store.init()
        elif not root.exists():
            raise FileNotFoundError(f"no store to reuse at {root}")
        return store

    def _workdir_for(self, episode: Episode, arm: Arm) -> pathlib.Path:
        """A clean room per run: no repository instructions reach the host by accident."""
        workdir = self._workspace / arm.name / episode.id / WORKDIR_NAME
        workdir.mkdir(parents=True, exist_ok=True)
        return workdir

    def _experience(
        self, store: Store, episode: Episode, arm: Arm, workdir: pathlib.Path
    ) -> ExperiencePhase:
        if arm.mode == MODE_NONE:
            return ExperiencePhase(calls=0, seconds=0.0, blocking_seconds=0.0, failures=0)

        batches = list(_batched(list(episode.sessions), self._batch))
        for index, batch in enumerate(batches):
            store.archive.append_session(f"{episode.id}-{index}", _render(batch))

        instructions = [framing.experience(arm.mode, _render(batch)) for batch in batches]
        workers = min(self._experience_workers, len(instructions)) or 1
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(
                pool.map(
                    lambda prompt: self._host.run(
                        prompt,
                        store_root=store.root,
                        tools_enabled=True,
                        system_prompt=prompts.MEMORY_KEEPER,
                        max_turns=WRITE_MAX_TURNS,
                        workdir=workdir,
                    ),
                    instructions,
                )
            )
        seconds = sum(result.seconds for result in results)
        return ExperiencePhase(
            calls=len(results),
            seconds=seconds,
            blocking_seconds=seconds if arm.blocking else 0.0,
            failures=len([result for result in results if not result.ok]),
        )

    def _assert_isolated(self, prompt: str, episode: Episode) -> None:
        """Checked before injection: what the store injects is memory the run itself wrote,
        which is the designed read track, not the transcript leaking into the exam."""
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
