"""Secret shapes that never enter stored or projected text."""

from __future__ import annotations

import re

# The value may be quoted — `password: "hunter2"`, `PASSWORD='s3cr3t'`, and JSON's
# `"api_key": "..."` all put a quote between the key and the colon. The opening quote is
# captured so the replacement can put it back and leave the line readable as config.
PREFIXED = re.compile(
    r"(?i)(bearer\s+|(?:api[_-]?key|token|password|secret)[\"']?\s*[=:]\s*)"
    r"(?:\"(?P<double>(?:\\[^\r\n]|[^\"\\\r\n])+|[^\"\r\n]+)\""
    r"|'(?P<single>(?:\\[^\r\n]|[^'\\\r\n])+|[^'\r\n]+)'"
    r"|\"(?P<double_open>(?:\\[^\r\n]|[^\"\\\r\n])*)(?=\r?\n|$)"
    r"|'(?P<single_open>(?:\\[^\r\n]|[^'\\\r\n])*)(?=\r?\n|$)"
    r"|(?P<value>[^\s,\"']+))"
)
NESTED_PREFIX = re.compile(
    r"(?i)(?:^|[\s|,{])(?:api[_-]?key|token|password|secret)[\"']?\s*[=:]\s*"
)
BARE = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\bgsk_[A-Za-z0-9]{16,}"),
    re.compile(r"\bhf_[A-Za-z0-9]{16,}"),
    re.compile(r"\bxai-[A-Za-z0-9]{16,}"),
    re.compile(r"\b\d{6,}\.[A-Za-z0-9]{24,}"),
)
REDACTED = "[REDACTED]"


def _redact_prefixed(match: re.Match[str]) -> str:
    double_closed = match["double"] is not None
    single_closed = match["single"] is not None
    quote = (
        '"'
        if double_closed or match["double_open"] is not None
        else ("'" if single_closed or match["single_open"] is not None else "")
    )
    closing = quote if double_closed or single_closed else ""
    return f"{match[1]}{quote}{REDACTED}{closing}"


def _redact_prefixed_values(text: str) -> str:
    """Redact keyed values, failing closed on a malformed second key in a quoted span."""
    pieces: list[str] = []
    cursor = 0
    while match := PREFIXED.search(text, cursor):
        pieces.append(text[cursor : match.start()])
        pieces.append(_redact_prefixed(match))
        cursor = match.end()
        quoted = match["double"] if match["double"] is not None else match["single"]
        if quoted is not None and NESTED_PREFIX.search(quoted):
            line_ends = [index for char in ("\r", "\n") if (index := text.find(char, cursor)) >= 0]
            cursor = min(line_ends) if line_ends else len(text)
    pieces.append(text[cursor:])
    return "".join(pieces)


def redact(text: str) -> str:
    cleaned = _redact_prefixed_values(text)
    for pattern in BARE:
        cleaned = pattern.sub(REDACTED, cleaned)
    return cleaned
