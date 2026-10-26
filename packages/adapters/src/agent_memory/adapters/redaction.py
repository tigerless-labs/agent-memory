"""Redaction of credential-shaped text before it is archived.

The archive is the input to distillation, so anything written there can end up
inside a long-lived memory entry. The observation path already redacts
prefixed secrets (``api_key=...``, ``Bearer ...``) via
``agent_memory.core.observation.bounded``, but bare provider keys such as
``sk-...`` do not match that pattern, and the archive path never went through
it in the first place.

This module owns the redaction used on the capture path. It is deliberately
independent of the observation helpers so that the archive, the distillation
prompt and the stored memory all see the same redacted text.
"""

from __future__ import annotations

import re

# Patterns are ordered: the more specific ones must run first.
_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # sk-ant-... before the generic sk-... pattern.
    (re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{16,}"), "sk-ant-***REDACTED***"),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}"), "sk-***REDACTED***"),
    (re.compile(r"\bgsk_[A-Za-z0-9]{16,}"), "gsk_***REDACTED***"),
    (re.compile(r"\bxai-[A-Za-z0-9]{16,}"), "xai-***REDACTED***"),
    (re.compile(r"\bhf_[A-Za-z0-9]{16,}"), "hf_***REDACTED***"),
    # Zhipu style: <numeric id>.<long secret>
    (re.compile(r"\b\d{6,}\.[A-Za-z0-9]{24,}"), "***REDACTED***"),
    # Prefixed assignments, mirroring the observation path but broader.
    (
        re.compile(
            r"(?i)(bearer\s+|"
            r"(?:api[_-]?key|apikey|access[_-]?token|secret[_-]?key|password|passwd|secret)"
            r"\s*[=:]\s*\"?'?)([^\s,\"']{8,})"
        ),
        r"\1***REDACTED***",
    ),
)

REDACTED = "***REDACTED***"


def redact(text: str) -> str:
    """Return ``text`` with credential-shaped substrings replaced."""
    if not text:
        return text
    out = text
    for pattern, replacement in _PATTERNS:
        out = pattern.sub(replacement, out)
    return out


def redact_all(items: list[str]) -> list[str]:
    """Redact every entry of a segment list."""
    return [redact(item) for item in items]
