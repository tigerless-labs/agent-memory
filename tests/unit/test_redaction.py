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
