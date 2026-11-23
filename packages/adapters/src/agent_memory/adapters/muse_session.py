"""Translate a root Muse session log into the adapter's plain conversation segments.

Muse's append-only envelope is a host implementation detail. This module is the only place
that knows it, and deliberately refuses child-session paths so observers and subagents are not
distilled as independent user conversations.
"""

from __future__ import annotations

import json
import os
import pathlib
import uuid

USER_KINDS = {"user", "user_message", "user_input", "prompt", "turn_input"}
ASSISTANT_KINDS = {
    "assistant",
    "assistant_message_committed",
    "assistant_message",
    "assistant_output",
    "final_answer",
    "model_output",
    "run_terminal",
}
TEXT_KEYS = ("text", "content", "message", "prompt", "last_assistant_message")
SESSION_LOG = "session.jsonl"


def path_for(
    session_id: str,
    environment: dict[str, str] | None = None,
    data_home: pathlib.Path | None = None,
) -> pathlib.Path | None:
    """Locate Muse 1.4's root log when its hook payload omits transcript_path."""
    if not session_id or pathlib.Path(session_id).name != session_id:
        return None
    try:
        uuid.UUID(session_id)
    except ValueError:
        return None
    env = os.environ if environment is None else environment
    fallback = pathlib.Path(env.get("HOME", "~")).expanduser() / ".local" / "share"
    data_home = data_home or pathlib.Path(env.get("XDG_DATA_HOME") or fallback)
    sessions = data_home / "muse" / "sessions"
    dated = sessions.glob(f"*/*/*/{session_id}/{SESSION_LOG}")
    return next((path for path in dated if path.is_file()), None)


def items(path: pathlib.Path) -> list[str]:
    if not path.exists() or "subagent" in path.parts:
        return []
    found: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").split("\n"):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        rendered = _conversation_item(record)
        if rendered and (not found or found[-1] != rendered):
            found.append(rendered)
    return found


def _conversation_item(record: object) -> str:
    if not isinstance(record, dict):
        return ""
    payload = record.get("payload", record)
    event = payload.get("event", payload) if isinstance(payload, dict) else payload
    if not isinstance(event, dict):
        return ""
    role = str(event.get("role") or event.get("kind") or "").lower()
    if role == "started" and payload.get("kind") == "run" and event.get("prompt"):
        role = "turn_input"
    if role == "run_terminal" and str(event.get("terminal") or "").lower() != "completed":
        return ""
    if role not in USER_KINDS | ASSISTANT_KINDS:
        return ""
    text = _text(event)
    if not text:
        return ""
    canonical_role = "user" if role in USER_KINDS else "assistant"
    return f"{canonical_role}: {text}"


def _text(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "\n".join(part for part in (_text(item) for item in value) if part)
    if isinstance(value, dict):
        for key in TEXT_KEYS:
            if key in value:
                rendered = _text(value[key])
                if rendered:
                    return rendered
    return ""
