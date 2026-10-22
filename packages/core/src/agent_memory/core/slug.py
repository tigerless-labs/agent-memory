"""Kebab slug = stable id. Survives any move, because nothing about it encodes location."""

from __future__ import annotations

import hashlib
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
    result = cleaned[:max_length].strip("-")
    if not result and text.strip():
        # Non-empty input that folds to nothing (pure non-ASCII like CJK,
        # Arabic, Cyrillic). Fall back to a content hash so every distinct
        # text produces a distinct, valid slug instead of colliding on an
        # empty string (issue #20).
        result = hashlib.sha256(text.encode("utf-8")).hexdigest()[:max_length]
    return result


def is_valid_slug(text: str) -> bool:
    return bool(VALID_SLUG.match(text))
