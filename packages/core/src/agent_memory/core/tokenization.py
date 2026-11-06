"""Optional CJK segmentation boundary. The production dependency is loaded on demand."""

from __future__ import annotations

import re

TOKENIZER_ASCII = "ascii"
TOKENIZER_CJK = "cjk"
SUPPORTED_TOKENIZERS = frozenset({TOKENIZER_ASCII, TOKENIZER_CJK})

INSTALL_HINT = "pip install 'agent-memory-core[cjk]'"

_ASCII_TOKENS = re.compile(r"[0-9A-Za-z_]+")
_MIN_CJK_QUERY_TOKEN_CHARS = 2


def _jieba():
    try:
        import jieba
    except ImportError as error:
        raise RuntimeError(
            "CJK tokenization is enabled but the optional segmentation dependency is "
            f"unavailable; install it with: {INSTALL_HINT}"
        ) from error
    return jieba


def validate_tokenizer(name: str) -> None:
    if name not in SUPPORTED_TOKENIZERS:
        raise ValueError(
            f"unknown tokenizer: {name!r}; expected one of {sorted(SUPPORTED_TOKENIZERS)}"
        )


def segment_text(text: str, tokenizer: str) -> str:
    """Index-side projection: space-joined tokens so unicode61 rows split on CJK words.

    Heading stays untouched — it is read back from the surface — but chunk text only
    feeds MATCH, so pre-segmented words are safe to store.
    """
    if tokenizer == TOKENIZER_CJK:
        return " ".join(token.strip() for token in _jieba().cut(text) if token.strip())
    return text


def query_tokens(query: str, tokenizer: str) -> list[str]:
    """Query-side tokens: ASCII literals always, plus CJK words of two or more characters.

    Single-character CJK tokens are dropped: they match nothing a two-character word
    has not already indexed, and they widen an OR expression with noise.
    """
    tokens = [token.lower() for token in _ASCII_TOKENS.findall(query)]
    if tokenizer == TOKENIZER_CJK:
        for token in _jieba().cut(query):
            token = token.strip()
            if token and not token.isascii() and len(token) >= _MIN_CJK_QUERY_TOKEN_CHARS:
                tokens.append(token.lower())
    return tokens
