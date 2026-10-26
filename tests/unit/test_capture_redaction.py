"""Redaction on the capture path: credentials never reach the archive.

The archive is the input to distillation, so a key left in cleartext there is
read back by the distiller and written into a long-lived memory entry. These
tests pin the redaction behaviour at the capture boundary.
"""

import pytest
from agent_memory.adapters import capture as capture_module
from agent_memory.adapters import redaction
from agent_memory.core import sessions

BARE_KEY = "sk-" + "a" * 32
ANTHROPIC_KEY = "sk-ant-api03-" + "b" * 32
GROQ_KEY = "gsk_" + "c" * 32
ZHIPU_KEY = "12345678." + "d" * 32


@pytest.mark.parametrize(
    "secret",
    [BARE_KEY, ANTHROPIC_KEY, GROQ_KEY, ZHIPU_KEY],
)
def test_bare_provider_keys_are_redacted(secret):
    assert secret not in redaction.redact(f"my key is {secret} ok")


@pytest.mark.parametrize(
    "text",
    [
        "api_key=" + BARE_KEY,
        "Bearer " + BARE_KEY,
        "token: " + BARE_KEY,
        "password=" + BARE_KEY,
    ],
)
def test_prefixed_secrets_are_redacted(text):
    assert BARE_KEY not in redaction.redact(text)


@pytest.mark.parametrize(
    "text",
    [
        "commit 489eb9df3c694ef1cb4669afa0a5ba4d5ad27728 merged",
        "md5 5d41402abc4b2a76b9719d911017c592",
        "sha256 08d39347d05946cd830c8a3b105eb1f5abcdef",
        "order 31028948 settled",
        "achievement 85% versus 92%",
    ],
)
def test_digests_and_ordinary_text_are_left_alone(text):
    assert redaction.redact(text) == text


def test_capture_redacts_before_anything_is_written(store):
    segments = [f"user: my key is {BARE_KEY}", "assistant: noted"]
    result = capture_module.capture(store, "session-secret", segments)

    assert BARE_KEY not in "".join(result.increment)
    archived = sessions.read(store.layout, "session-secret")
    assert BARE_KEY not in "".join(message.text for message in archived)
    assert any("***REDACTED***" in message.text for message in archived)


def test_capture_keeps_the_redacted_text_consistent_with_the_archive(store):
    segments = [f"user: key {BARE_KEY}", "assistant: ok"]
    result = capture_module.capture(store, "session-consistent", segments)
    archived = sessions.read(store.layout, "session-consistent")

    # sessions.read strips the "role: " prefix, capture keeps it.
    assert [message.text for message in archived] == [
        segment.split(": ", 1)[1] for segment in result.increment
    ]


def test_redaction_does_not_break_the_watermark(store):
    segments = [f"user: key {BARE_KEY}", "assistant: ok"]
    capture_module.capture(store, "session-watermark", segments)
    assert capture_module.capture(store, "session-watermark", segments).is_empty()


def test_ordinary_segments_are_archived_unchanged(store):
    segments = ["user: we moved the deploy to Fridays", "assistant: noted"]
    result = capture_module.capture(store, "session-plain", segments)
    assert result.increment == tuple(segments)
