"""Splits an increment on message boundaries so one distillation call never grows unbounded."""

from __future__ import annotations

from .sessions import Message


def batches(messages: list[Message], max_chars: int) -> list[list[Message]]:
    """Consecutive messages packed up to a size; a single oversized message stands alone."""
    found: list[list[Message]] = []
    current: list[Message] = []
    size = 0
    for message in messages:
        length = len(message.text)
        if current and size + length > max_chars:
            found.append(current)
            current = []
            size = 0
        current.append(message)
        size += length
    if current:
        found.append(current)
    return found
