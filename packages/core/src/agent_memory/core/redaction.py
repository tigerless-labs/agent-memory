"""Secret shapes that never enter stored or projected text."""

from __future__ import annotations

import re

# The value may be quoted — `password: "hunter2"`, `PASSWORD='s3cr3t'`, and JSON's
# `"api_key": "..."` all put a quote between the key and the colon. The opening quote is
# captured so the replacement can put it back and leave the line readable as config.
PREFIXED = re.compile(
    r"(?i)(bearer\s+|(?:api[_-]?key|token|password|secret)[\"']?\s*[=:]\s*)"
    r"(?P<quote>[\"']?)(?P<value>[^\s,\"']+)(?P=quote)"
)
BARE = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\bgsk_[A-Za-z0-9]{16,}"),
    re.compile(r"\bhf_[A-Za-z0-9]{16,}"),
    re.compile(r"\bxai-[A-Za-z0-9]{16,}"),
)
REDACTED = "[REDACTED]"


def redact(text: str) -> str:
    cleaned = PREFIXED.sub(rf"\1\g<quote>{REDACTED}\g<quote>", text)
    for pattern in BARE:
        cleaned = pattern.sub(REDACTED, cleaned)
    return cleaned
