"""Where a run may write. A worktree is an isolation for code, never for corpora.

Worktree paths and run artefacts are both gitignored, and `git worktree remove` does not
refuse over ignored files — status is clean, the removal succeeds, and hours of write pass
go with it. The lifecycle then says to remove a worktree as soon as its branch lands, so a
run that wrote there is scheduled for deletion by the rules the project already follows.
"""

from __future__ import annotations

import pathlib

WORKTREE_MARKER = (".claude", "worktrees")

REFUSAL = (
    "{path} is inside a worktree ({marker}). A worktree and everything gitignored inside it "
    "is deleted by `git worktree remove` without warning, and the lifecycle removes one as "
    "soon as its branch lands. Point this at the main working tree instead, by absolute path."
)


class DisposableWorkspace(ValueError):
    """A write was aimed at a directory the project deletes on purpose."""


def for_writing(raw: str | pathlib.Path) -> pathlib.Path:
    path = pathlib.Path(raw).expanduser().resolve()
    parts = path.parts
    for index in range(len(parts) - 1):
        if parts[index : index + len(WORKTREE_MARKER)] == WORKTREE_MARKER:
            raise DisposableWorkspace(
                REFUSAL.format(path=path, marker="/".join(WORKTREE_MARKER))
            )
    return path
