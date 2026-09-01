"""Two universal moments, three host dialects. The dialect table is the whole adapter."""

from __future__ import annotations

MOMENT_INJECT = "inject"
MOMENT_PAUSE = "pause"
MOMENT_EVICT = "evict"

HOST_CLAUDE_CODE = "claude-code"
HOST_CODEX = "codex"
HOST_GENERIC = "generic"

DIALECTS: dict[str, dict[str, str]] = {
    HOST_CLAUDE_CODE: {
        "SessionStart": MOMENT_INJECT,
        "Stop": MOMENT_PAUSE,
        "SessionEnd": MOMENT_PAUSE,
        "PreCompact": MOMENT_EVICT,
    },
    HOST_CODEX: {
        "session_start": MOMENT_INJECT,
        "turn_end": MOMENT_PAUSE,
        "session_end": MOMENT_PAUSE,
        "context_compaction": MOMENT_EVICT,
    },
    HOST_GENERIC: {
        MOMENT_INJECT: MOMENT_INJECT,
        MOMENT_PAUSE: MOMENT_PAUSE,
        MOMENT_EVICT: MOMENT_EVICT,
    },
}


def moment_for(host: str, event: str) -> str | None:
    return DIALECTS.get(host, {}).get(event)


def hosts() -> tuple[str, ...]:
    return tuple(DIALECTS)
