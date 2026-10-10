"""CJK-aware tokenization for the lexical surfaces.

Markdown truth stays untouched: segmentation is a projection concern, applied where text
enters the FTS index and where a query becomes a match expression. jieba is optional; a
bigram fallback keeps CJK recall working without it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

_ASCII_TOKEN = re.compile(r"[0-9A-Za-z_]+")
CJK_RANGES = "\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af\uf900-\ufaff"
_CJK_RUN = re.compile(f"[{CJK_RANGES}]+")
_CJK_SPLIT = re.compile(f"([{CJK_RANGES}]+)")
_TOKEN = re.compile(f"(?:[0-9A-Za-z_]+|[{CJK_RANGES}]+)")
_KEY_CHARS = re.compile(f"[0-9a-z{CJK_RANGES}]+")

JIEBA_LOG_LEVEL = 40
BIGRAM_WIDTH = 2
FULL_RUN_MAX_CHARS = 4

try:
    import jieba as _jieba
except ImportError:  # pragma: no cover - the fallback path is what runs here
    _jieba = None
else:
    _jieba.setLogLevel(JIEBA_LOG_LEVEL)  # keep the stdio transport's stderr quiet


def has_cjk(text: str) -> bool:
    return bool(_CJK_RUN.search(text))


def _fallback_run(run: str) -> list[str]:
    bigrams = [
        run[index : index + BIGRAM_WIDTH] for index in range(len(run) - BIGRAM_WIDTH + 1)
    ]
    if not bigrams:
        return [run]
    if len(run) <= FULL_RUN_MAX_CHARS:
        bigrams.append(run)
    return bigrams


def _fallback_pieces(text: str) -> list[str]:
    pieces: list[str] = []
    for part in _CJK_SPLIT.split(text):
        if not part:
            continue
        if _CJK_RUN.fullmatch(part):
            pieces.extend(_fallback_run(part))
        else:
            pieces.extend(_ASCII_TOKEN.findall(part))
    return pieces


def _clean(pieces: Iterable[str]) -> list[str]:
    lowered = [piece.strip().lower() for piece in pieces]
    return [token for token in dict.fromkeys(lowered) if _TOKEN.fullmatch(token)]


def segment(text: str) -> str:
    """Space-separate CJK words so FTS5's default tokenizer can index them."""
    if not text or not has_cjk(text):
        return text
    if _jieba is not None:
        return " ".join(_jieba.cut_for_search(text))
    return _CJK_RUN.sub(lambda match: " ".join(_fallback_run(match.group())), text)


def query_tokens(query: str) -> list[str]:
    """Tokens a query contributes to a match expression; ASCII-only queries behave as before."""
    if not query:
        return []
    if not has_cjk(query):
        return list(dict.fromkeys(token.lower() for token in _ASCII_TOKEN.findall(query)))
    pieces = _jieba.cut_for_search(query) if _jieba is not None else _fallback_pieces(query)
    return _clean(pieces)


def word_tokens(text: str) -> list[str]:
    """Words for similarity-style comparisons: no search subwords, no stopword policy."""
    if not text:
        return []
    if not has_cjk(text):
        return _ASCII_TOKEN.findall(text.lower())
    pieces = _jieba.cut(text) if _jieba is not None else _fallback_pieces(text)
    return _clean(pieces)


def compact_key(text: str) -> str:
    """CJK and ASCII characters with separators removed; the identity key for groups."""
    return "".join(_KEY_CHARS.findall(text.lower()))
