"""One store, several hosts: what A writes, B must be able to read.

This is the generality claim stated as a measurement. It does not ask whether a host answers
well — only whether the store is common ground: a memory written through one host's shell is
found, verbatim, through another's.
"""

from __future__ import annotations

import dataclasses
import pathlib

from agent_memory.core import prompts
from agent_memory.core.store import Store

from .hosts import Host

WRITE_TASK = """Record this exactly, as one memory in the user domain:

{fact}

Use the mem CLI. Reply with the name of the entry you created."""

READ_TASK = """Search your memory store for what it says about {subject}.

Reply with the sentence you find, and nothing else."""

WORKDIR_NAME = "cwd"
STORE_NAME = "store"


@dataclasses.dataclass(frozen=True)
class Fact:
    subject: str
    sentence: str
    token: str


@dataclasses.dataclass(frozen=True)
class InteropResult:
    writer: str
    reader: str
    wrote: bool
    read: bool
    memories: int
    answer: str
    error: str

    @property
    def passed(self) -> bool:
        return self.wrote and self.read

    def as_dict(self) -> dict[str, object]:
        return dataclasses.asdict(self) | {"passed": self.passed}


def check(writer: Host, reader: Host, fact: Fact, workspace: pathlib.Path) -> InteropResult:
    root = workspace / f"{writer.name}--to--{reader.name}"
    store = Store(root / STORE_NAME, agent="interop")
    store.init()
    workdir = root / WORKDIR_NAME
    workdir.mkdir(parents=True, exist_ok=True)

    written = writer.run(
        WRITE_TASK.format(fact=fact.sentence),
        store_root=store.root,
        tools_enabled=True,
        system_prompt=prompts.memory_keeper(),
        max_turns=WRITE_TURNS,
        workdir=workdir,
    )
    store.sync_index()
    memories = len(store.records())
    if not written.ok or memories == 0:
        return InteropResult(
            writer=writer.name, reader=reader.name, wrote=False, read=False,
            memories=memories, answer="", error=written.error or "wrote nothing",
        )

    recalled = reader.run(
        READ_TASK.format(subject=fact.subject),
        store_root=store.root,
        tools_enabled=True,
        system_prompt=prompts.memory_keeper(),
        max_turns=READ_TURNS,
        workdir=workdir,
    )
    return InteropResult(
        writer=writer.name,
        reader=reader.name,
        wrote=True,
        read=recalled.ok and fact.token.lower() in recalled.text.lower(),
        memories=memories,
        answer=recalled.text[:ANSWER_EXCERPT],
        error=recalled.error,
    )


def matrix(hosts: list[Host], fact: Fact, workspace: pathlib.Path) -> list[InteropResult]:
    return [
        check(writer, reader, fact, workspace)
        for writer in hosts
        for reader in hosts
    ]


def render(results: list[InteropResult]) -> str:
    names = sorted({result.reader for result in results})
    lines = ["| writer \\ reader | " + " | ".join(names) + " |", "|---" * (len(names) + 1) + "|"]
    for writer in sorted({result.writer for result in results}):
        cells = []
        for reader in names:
            found = next(
                (r for r in results if r.writer == writer and r.reader == reader), None
            )
            cells.append("—" if found is None else ("pass" if found.passed else "FAIL"))
        lines.append(f"| {writer} | " + " | ".join(cells) + " |")
    failures = [result for result in results if not result.passed]
    lines.append("")
    lines.append(f"{len(results) - len(failures)}/{len(results)} pairs interoperate")
    for failure in failures:
        detail = failure.error or failure.answer
        lines.append(f"  {failure.writer} -> {failure.reader}: {detail[:FAILURE_EXCERPT]}")
    return "\n".join(lines)


ANSWER_EXCERPT = 300
FAILURE_EXCERPT = 160
WRITE_TURNS = 20
READ_TURNS = 20
