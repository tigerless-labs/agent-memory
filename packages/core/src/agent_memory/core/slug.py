"""Kebab slug = stable id. Survives any move, because nothing about it encodes location."""

from __future__ import annotations

import re
import unicodedata

_SEPARATORS = re.compile(r"[\s_/\\.]+")
_ILLEGAL = re.compile(r"[^a-z0-9-]+")
_RUNS = re.compile(r"-+")
VALID_SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def slugify(text: str, max_length: int) -> str:
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    lowered = _SEPARATORS.sub("-", folded.strip().lower())
    cleaned = _RUNS.sub("-", _ILLEGAL.sub("-", lowered)).strip("-")
    if cleaned:
        return cleaned[:max_length].strip("-")
    # Non-ASCII-only input produces an empty fold. Fall back to a stable
    # digest so the slug is non-empty and deterministic across calls.
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:max_length]


def is_valid_slug(text: str) -> bool:
    return bool(VALID_SLUG.match(text))
