"""Read a host transcript into plain segments. Nothing here interprets what it reads."""

from __future__ import annotations

import json
import pathlib

TEXT_KEYS = ("text", "content", "summary")
ROLE_KEYS = ("role", "type")


def items(path: pathlib.Path) -> list[str]:
    if not path.exists():
        return []
    found: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            entry = json.loads(stripped)
        except json.JSONDecodeError:
            found.append(stripped)
            continue
        rendered = _render(entry)
        if rendered:
            found.append(rendered)
    return found


def _render(entry: object) -> str:
    if isinstance(entry, str):
        return entry.strip()
    if not isinstance(entry, dict):
        return ""
    role = next((str(entry[key]) for key in ROLE_KEYS if entry.get(key)), "")
    message = entry.get("message")
    body = _text(message if message is not None else entry)
    if not body:
        return ""
    return f"{role}: {body}".strip(": ").strip()


def _text(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "\n".join(part for part in (_text(item) for item in value) if part)
    if isinstance(value, dict):
        for key in TEXT_KEYS:
            if key in value:
                return _text(value[key])
    return ""
