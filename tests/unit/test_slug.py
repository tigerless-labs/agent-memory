"""Tests for agent_memory.core.slug — kebab-case slug generation and validation."""

from __future__ import annotations

from agent_memory.core.slug import is_valid_slug, slugify


class TestSlugifyAscii:
    """Existing ASCII behaviour must remain unchanged."""

    def test_plain_text(self) -> None:
        assert slugify("Hello World", 50) == "hello-world"

    def test_separators_normalised(self) -> None:
        assert slugify("a_b/c.d", 50) == "a-b-c-d"

    def test_illegal_chars_stripped(self) -> None:
        assert slugify("hello!@#world", 50) == "hello-world"

    def test_consecutive_dashes_collapsed(self) -> None:
        assert slugify("a---b", 50) == "a-b"

    def test_leading_trailing_dashes_trimmed(self) -> None:
        assert slugify("--hello--", 50) == "hello"

    def test_truncation(self) -> None:
        result = slugify("hello world", 5)
        assert result == "hello"
        assert len(result) <= 5

    def test_empty_input_returns_empty(self) -> None:
        assert slugify("", 50) == ""

    def test_whitespace_only_returns_empty(self) -> None:
        assert slugify("   ", 50) == ""


class TestSlugifyNonAsciiFallback:
    """Pure non-ASCII input must produce a non-empty, distinct, valid slug."""

    def test_cjk_returns_non_empty(self) -> None:
        result = slugify("你好世界", 50)
        assert result, "CJK input must not produce an empty slug"
        assert is_valid_slug(result)

    def test_arabic_returns_non_empty(self) -> None:
        result = slugify("مرحبا بالعالم", 50)
        assert result, "Arabic input must not produce an empty slug"
        assert is_valid_slug(result)

    def test_cyrillic_returns_non_empty(self) -> None:
        result = slugify("Привет мир", 50)
        assert result, "Cyrillic input must not produce an empty slug"
        assert is_valid_slug(result)

    def test_distinct_inputs_distinct_slugs(self) -> None:
        a = slugify("你好世界", 50)
        b = slugify("再见世界", 50)
        assert a != b, "different non-ASCII texts must not collide"

    def test_same_input_same_slug(self) -> None:
        assert slugify("你好世界", 50) == slugify("你好世界", 50)

    def test_fallback_respects_max_length(self) -> None:
        result = slugify("你好世界", 16)
        assert len(result) <= 16
        assert is_valid_slug(result)

    def test_fallback_is_hex_digest(self) -> None:
        result = slugify("你好世界", 64)
        # SHA-256 hex digest is 64 hex chars
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)


class TestSlugifyMixed:
    """Mixed ASCII/non-ASCII should prefer the ASCII fold when possible."""

    def test_mixed_uses_ascii_fold(self) -> None:
        # "hello 世界" folds to "hello " -> "hello"
        assert slugify("hello 世界", 50) == "hello"

    def test_mixed_with_only_punctuation_ascii_falls_back(self) -> None:
        # "!!!你好" has no ASCII alphanumerics after folding
        result = slugify("!!!你好", 50)
        assert result
        assert is_valid_slug(result)


class TestIsValidSlug:
    def test_valid(self) -> None:
        assert is_valid_slug("hello-world")
        assert is_valid_slug("a")
        assert is_valid_slug("a1-b2")

    def test_invalid(self) -> None:
        assert not is_valid_slug("")
        assert not is_valid_slug("-hello")
        assert not is_valid_slug("hello-")
        assert not is_valid_slug("hello--world")
        assert not is_valid_slug("Hello_World")
