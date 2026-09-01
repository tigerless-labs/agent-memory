"""The W options under test (ADR-006). R is identical across every one of them."""

from __future__ import annotations

import dataclasses

MODE_NONE = "none"
MODE_BOUNDARY = "boundary"
MODE_INLINE = "inline"
MODE_COLD = "cold"


@dataclasses.dataclass(frozen=True)
class Arm:
    name: str
    mode: str
    memory: bool
    blocking: bool
    description: str

    def writes(self) -> bool:
        return self.mode != MODE_NONE


W0 = Arm("W0", MODE_NONE, memory=False, blocking=False, description="no memory (control)")
W1 = Arm(
    "W1",
    MODE_BOUNDARY,
    memory=True,
    blocking=True,
    description="boundary self-write, blocking the task tail",
)
W2 = Arm(
    "W2",
    MODE_BOUNDARY,
    memory=True,
    blocking=False,
    description="boundary fork, distilled off the task's critical path",
)
W3 = Arm(
    "W3",
    MODE_COLD,
    memory=True,
    blocking=False,
    description="cold read of the archived transcript, after the fact",
)
W4 = Arm(
    "W4",
    MODE_INLINE,
    memory=True,
    blocking=True,
    description="inline write while the conversation is still running",
)

ALL = (W0, W1, W2, W3, W4)
BY_NAME = {arm.name: arm for arm in ALL}


def parse(names: str) -> list[Arm]:
    return [BY_NAME[name.strip()] for name in names.split(",") if name.strip()]
