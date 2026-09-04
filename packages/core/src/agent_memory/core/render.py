"""The conversation as the executor sees it: numbered lines under one session time.

Numbering is what lets a memory cite a message range instead of quoting it. The session time
anchors every relative date the conversation contains.
"""

from __future__ import annotations

from . import timestamp
from .sessions import Message

HEADER = "## Conversation"
TIME_LINE = "Session time: {span} ({weekday}). Relative times such as 'last week' count from it."
LINE = "[{index}][{role}]: {text}"
ROLE_UNKNOWN = "message"
SPAN_SEPARATOR = " to "


def conversation(messages: list[Message]) -> str:
    stamped = [message.at for message in messages if message.at]
    lines = [HEADER]
    if stamped:
        first = timestamp.parse(stamped[0])
        last = timestamp.parse(stamped[-1])
        span = timestamp.render(first)
        if last != first:
            span += SPAN_SEPARATOR + timestamp.render(last)
        lines.append(TIME_LINE.format(span=span, weekday=first.strftime("%A")))
    lines.append("")
    for message in messages:
        lines.append(
            LINE.format(
                index=message.index,
                role=message.role or ROLE_UNKNOWN,
                text=message.text.replace("\n", "\n    "),
            )
        )
    return "\n".join(lines)
