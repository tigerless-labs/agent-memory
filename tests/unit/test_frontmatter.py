"""Frontmatter dialect: parse and render round-trip, including inline arrays."""

import pytest
from agent_memory.core import frontmatter


def _round_trip(fields, body):
    text = frontmatter.render(fields, body)
    parsed_fields, parsed_body = frontmatter.parse(text)
    return parsed_fields, parsed_body


def test_parse_returns_empty_dict_when_no_frontmatter():
    fields, body = frontmatter.parse("just body text\n")
    assert fields == {}
    assert body == "just body text\n"


def test_parse_round_trip_preserves_scalar_fields():
    fields = {"name": "test-entry", "status": "active", "weight": 1.5}
    parsed, _ = _round_trip(fields, "body content")
    assert parsed["name"] == "test-entry"
    assert parsed["status"] == "active"
    assert parsed["weight"] == 1.5


def test_inline_array_of_quoted_strings_round_trips():
    fields = {"links": ["slug-one", "slug-two"]}
    parsed, _ = _round_trip(fields, "body")
    assert parsed["links"] == ["slug-one", "slug-two"]


def test_inline_array_with_unquoted_value_containing_apostrophe():
    """An unquoted value with a quote character mid-value must not enter quote mode.

    Before the fix, the apostrophe in 'it's' toggled quote tracking on,
    which prevented the comma from splitting the next item correctly.
    """
    text = "---\nlinks: [it's, done]\n---\nbody\n"
    fields, body = frontmatter.parse(text)
    assert fields["links"] == ["it's", "done"]


def test_inline_array_with_quoted_value_containing_other_quote_type():
    """A double-quoted value containing a single quote must round-trip."""
    text = '---\nlinks: ["it\'s done", "hello"]\n---\nbody\n'
    fields, body = frontmatter.parse(text)
    assert fields["links"] == ["it's done", "hello"]


def test_inline_array_single_unquoted_value_with_apostrophe():
    text = "---\ntags: [it's]\n---\nbody\n"
    fields, body = frontmatter.parse(text)
    assert fields["tags"] == ["it's"]


def test_empty_inline_array():
    fields = {"links": []}
    parsed, _ = _round_trip(fields, "body")
    assert parsed["links"] == []


def test_render_wraps_strings_needing_quoting():
    rendered = frontmatter._render_scalar("hello: world")
    assert rendered == '"hello: world"'


def test_render_scalar_boolean_and_null():
    assert frontmatter._render_scalar(True) == "true"
    assert frontmatter._render_scalar(False) == "false"
    assert frontmatter._render_scalar(None) == "null"


def test_split_document_with_no_closing_delimiter_returns_none_header():
    header, body = frontmatter.split_document("---\nname: test\nno closing marker\n")
    assert header is None


STRINGS_THAT_LOOK_LIKE_OTHER_SCALARS = [
    "true",
    "False",
    "null",
    "~",
    "42",
    "1e3",
    "infinity",
    "nan",
    "",
    " padded ",
    '"quoted"',
    "'single'",
    "[bracketed]",
    '"leading quote only',
    "'dangling",
]
STRINGS_WITH_QUOTES_AND_BACKSLASHES = [
    'Note: he said "hi"',
    "ends with a backslash: \\",
    'C:\\tmp, then "x"',
    '\\"',
]


@pytest.mark.parametrize(
    "value", STRINGS_THAT_LOOK_LIKE_OTHER_SCALARS + STRINGS_WITH_QUOTES_AND_BACKSLASHES
)
def test_string_scalar_round_trips_unchanged(value):
    parsed, _ = _round_trip({"abstract": value}, "body")
    assert parsed["abstract"] == value


@pytest.mark.parametrize(
    "value", STRINGS_THAT_LOOK_LIKE_OTHER_SCALARS + STRINGS_WITH_QUOTES_AND_BACKSLASHES
)
def test_repeated_rewrites_are_a_fixed_point(value):
    first = frontmatter.render({"abstract": value}, "body")
    second = frontmatter.render(frontmatter.parse(first)[0], "body")
    assert second == first


def test_inline_array_items_with_quotes_and_commas_round_trip():
    links = ['x "y", z', "true", '"abc', "plain", "a\\b"]
    parsed, _ = _round_trip({"links": links}, "body")
    assert parsed["links"] == links


def test_escaped_quote_written_by_earlier_renders_reads_as_a_quote():
    text = '---\nabstract: "Note: he said \\"hi\\""\n---\nbody\n'
    fields, _ = frontmatter.parse(text)
    assert fields["abstract"] == 'Note: he said "hi"'


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('"C:\\"', "C:\\"),
        ('"C:\\tmp, x"', "C:\\tmp, x"),
        ('"C:\\tmp: x"', "C:\\tmp: x"),
        ('"ends with \\"', "ends with \\"),
    ],
)
def test_a_lone_backslash_written_by_earlier_renders_is_kept(raw, expected):
    fields, _ = frontmatter.parse(f"---\nabstract: {raw}\n---\nbody\n")
    assert fields["abstract"] == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('["C:\\", next]', ["C:\\", "next"]),
        ('["C:\\", "x"]', ["C:\\", "x"]),
    ],
)
def test_inline_array_with_a_lone_backslash_from_earlier_renders_splits(raw, expected):
    fields, _ = frontmatter.parse(f"---\nlinks: {raw}\n---\nbody\n")
    assert fields["links"] == expected


def test_inline_array_item_containing_quote_comma_round_trips():
    links = ['a", b', "next", 'C:\\", "x']
    parsed, _ = _round_trip({"links": links}, "body")
    assert parsed["links"] == links
