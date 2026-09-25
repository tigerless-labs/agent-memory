"""Translate a root Muse session log into the adapter's plain conversation segments.

Muse's append-only envelope is a host implementation detail. This module is the only place
that knows it, and deliberately refuses child-session paths so observers and subagents are not
distilled as independent user conversations.
"""

from __future__ import annotations

import json
import pathlib

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


def items(path: pathlib.Path) -> list[str]:
    if not path.exists() or "subagent" in path.parts:
        return []
    found: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
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
