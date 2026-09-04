"""When a session's archived backlog is worth a distillation call.

Every trigger means the same thing — distill what the archive holds past the last
distillation — so a hook that never fires costs latency, never knowledge (Invariant 4).
"""

from __future__ import annotations

import dataclasses

from . import sessions, timestamp
from .config import WriteConfig
from .paths import StoreLayout
from .sessions import Message
from .watermark import Mark, Watermark

REASON_BOUNDARY = "boundary"
REASON_MESSAGES = "messages"
REASON_TOKENS = "tokens"
REASON_IDLE = "idle"
REASON_FORCED = "forced"


@dataclasses.dataclass(frozen=True)
class Due:
    session: str
    reason: str
    messages: tuple[Message, ...]


def backlog(layout: StoreLayout, session: str, watermark: Watermark) -> list[Message]:
    mark = watermark.read(session)
    return [
        message for message in sessions.read(layout, session) if message.index >= mark.distilled
    ]


def reason_for(
    config: WriteConfig, mark: Mark, messages: list[Message], now_iso: str, boundary: bool
) -> str | None:
    if not messages:
        return None
    if boundary:
        return REASON_BOUNDARY
    if len(messages) >= config.pending_message_threshold:
        return REASON_MESSAGES
    chars = sum(len(message.text) for message in messages)
    if chars >= config.pending_token_threshold * config.chars_per_token:
        return REASON_TOKENS
    if mark.updated_at and now_iso:
        idle = timestamp.parse(now_iso) - timestamp.parse(mark.updated_at)
        if idle.total_seconds() >= config.idle_seconds:
            return REASON_IDLE
    return None
