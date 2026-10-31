"""Bare provider keys must not reach the archive or the distill prompt."""

import json

from agent_memory.adapters.capture import capture
from agent_memory.core import sessions

BARE_KEYS = (
    "sk-ant-api03-Aa1Bb2Cc3Dd4Ee5Ff6Gg7Hh8",
    "sk-proj-Aa1Bb2Cc3Dd4Ee5Ff6Gg7Hh8",
    "gsk_Aa1Bb2Cc3Dd4Ee5Ff6Gg7Hh8",
    "hf_Aa1Bb2Cc3Dd4Ee5Ff6Gg7Hh8",
    "xai-Aa1Bb2Cc3Dd4Ee5Ff6Gg7Hh8",
)
DIGEST = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"


def archived_text(store, session: str) -> str:
    path = sessions.session_path(store.layout, session)
    lines = path.read_text(encoding="utf-8").splitlines()
    return "\n".join(json.loads(line)["text"] for line in lines if line.strip())


def test_bare_provider_keys_never_reach_the_archive(store):
    items = [f"here is my key {key}, remember it" for key in BARE_KEYS]

    capture(store, "bare-keys", items)

    stored = archived_text(store, "bare-keys")
    for key in BARE_KEYS:
        assert key not in stored
    assert stored.count("[REDACTED]") == len(BARE_KEYS)


def test_bare_provider_keys_never_reach_the_distill_prompt(store):
    result = capture(store, "bare-prompt", [f"here is my key {BARE_KEYS[0]}"])

    for key in BARE_KEYS:
        assert key not in result.instruction


def test_prefixed_secrets_are_still_redacted_in_the_archive(store):
    capture(store, "prefixed", ["api_key=plain-value-here and Bearer plain-token-here"])

    stored = archived_text(store, "prefixed")
    assert "plain-value-here" not in stored
    assert "plain-token-here" not in stored


def test_quoted_secrets_never_reach_the_archive(store):
    capture(
        store,
        "quoted",
        ['password: "hunter2"', "PASSWORD='s3cr3t'", '{"api_key": "abcd1234efgh5678"}'],
    )

    stored = archived_text(store, "quoted")
    for secret in ("hunter2", "s3cr3t", "abcd1234efgh5678"):
        assert secret not in stored
    assert stored.count("[REDACTED]") == 3


def test_hex_digests_survive_redaction(store):
    capture(store, "digest", [f"the sha256 of the artefact is {DIGEST}"])

    assert DIGEST in archived_text(store, "digest")
