"""Quoted values are how .env, YAML and JSON spell a credential; they must not survive."""

import pytest
from agent_memory.core.redaction import REDACTED, redact


@pytest.mark.parametrize(
    ("line", "secret"),
    [
        ('password: "hunter2"', "hunter2"),
        ("password: 'hunter2'", "hunter2"),
        ('export PASSWORD="s3cr3t"', "s3cr3t"),
        ('{"api_key": "abcd1234efgh5678"}', "abcd1234efgh5678"),
        ('token = "ghp_Aa1Bb2Cc3Dd4Ee5Ff6Gg7Hh8"', "ghp_Aa1Bb2Cc3Dd4Ee5Ff6Gg7Hh8"),
        ("secret='a-b_c.d'", "a-b_c.d"),
    ],
)
def test_a_quoted_value_is_redacted(line, secret):
    cleaned = redact(line)

    assert secret not in cleaned
    assert REDACTED in cleaned


def test_the_quote_is_kept_so_the_line_still_reads_as_config():
    assert redact('password: "hunter2"') == 'password: "[REDACTED]"'
    assert redact("password: 'hunter2'") == "password: '[REDACTED]'"


def test_an_unquoted_value_is_still_redacted():
    assert redact("api_key=plain-value-here") == "api_key=[REDACTED]"
    assert redact("Authorization: Bearer plain-token-here") == "Authorization: Bearer [REDACTED]"


def test_a_quoted_value_without_a_colon_is_not_touched():
    assert redact('the string "hunter2" appears alone') == 'the string "hunter2" appears alone'


@pytest.mark.parametrize(
    ("line", "secret"),
    [
        ('password: "correct horse battery staple"', "horse"),
        ("PASSWORD='my secret phrase'", "secret phrase"),
        ('{"password": "pa,ss word"}', "pa,ss"),
        ('{"api_key": "abc,def123"}', "def123"),
        ('secret = "it\'s a secret"', "a secret"),
    ],
)
def test_a_quoted_value_with_spaces_or_commas_is_redacted_whole(line, secret):
    cleaned = redact(line)

    assert secret not in cleaned
    assert REDACTED in cleaned


def test_a_quoted_value_with_spaces_keeps_its_quotes_and_the_rest_of_the_line():
    assert redact('password: "a b c" and more') == 'password: "[REDACTED]" and more'
    assert redact('{"token": "a b", "user": "ann"}') == '{"token": "[REDACTED]", "user": "ann"}'


def test_an_escaped_quote_does_not_end_a_quoted_value():
    assert redact(r'{"password": "say \"hi\" now"}') == '{"password": "[REDACTED]"}'
    assert redact(r"secret: 'it\'s a b'") == "secret: '[REDACTED]'"


def test_a_trailing_backslash_still_ends_a_quoted_value():
    assert redact(r'password: "C:\dir\"') == 'password: "[REDACTED]"'


def test_an_empty_quoted_value_is_left_alone():
    assert redact('password: ""') == 'password: ""'


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ('password: "unterminated', 'password: "[REDACTED]'),
        ("secret = 'truncated phrase", "secret = '[REDACTED]"),
        ('password: "unterminated\nuser=ann', 'password: "[REDACTED]\nuser=ann'),
    ],
)
def test_an_unterminated_quoted_value_is_redacted_to_the_line_end(line, expected):
    assert redact(line) == expected


def test_a_malformed_second_key_cannot_leave_its_value_visible():
    cleaned = redact('api_key: "abc | secret: "xyz"')

    assert "abc" not in cleaned
    assert "xyz" not in cleaned
    assert cleaned == 'api_key: "[REDACTED]"'
