"""M4 — the watermark makes triggers optional, and hooks harmless when they misbehave."""

import io
import json

import pytest
from agent_memory.adapters import capture as capture_module
from agent_memory.adapters import hook_entry, moments, setup, transcript
from agent_memory.core import injection
from agent_memory.core.watermark import Watermark

SEGMENTS = ["user: we moved the deploy to Fridays", "assistant: noted", "user: and E4021 is fixed"]


def test_repeated_triggers_hand_over_only_the_increment(store):
    first = capture_module.capture(store, "session-a", SEGMENTS[:2])
    assert first.increment == tuple(SEGMENTS[:2])

    capture_module.commit(store, "session-a", len(SEGMENTS[:2]))
    second = capture_module.capture(store, "session-a", SEGMENTS)
    assert second.increment == (SEGMENTS[-1],)

    capture_module.commit(store, "session-a", len(SEGMENTS))
    assert capture_module.capture(store, "session-a", SEGMENTS).is_empty()


def test_a_kill_before_commit_leaves_the_tail_to_be_picked_up_again(store):
    capture_module.capture(store, "session-b", SEGMENTS)
    recovered = capture_module.capture(store, "session-b", SEGMENTS)
    assert recovered.increment == tuple(SEGMENTS)


def test_the_watermark_never_moves_backwards(store):
    watermark = Watermark(store.layout, store.clock)
    watermark.advance("session-c", len(SEGMENTS))
    assert watermark.advance("session-c", 1).consumed == len(SEGMENTS)


def test_captured_material_is_archived_even_when_nothing_is_distilled(store):
    result = capture_module.capture(store, "session-d", SEGMENTS)
    archived = store.layout.sessions / "session-d.jsonl"
    assert archived.exists()
    assert SEGMENTS[-1].split(": ", 1)[1] in archived.read_text(encoding="utf-8")
    assert result.instruction


def test_the_cron_path_reaches_the_same_state_as_the_hook_path(store, tmp_path):
    hook_state = capture_module.capture(store, "via-hook", SEGMENTS)
    capture_module.commit(store, "via-hook", len(hook_state.increment))

    cron_state = capture_module.capture(store, "via-cron", SEGMENTS)
    capture_module.commit(store, "via-cron", len(cron_state.increment))

    assert hook_state.increment == cron_state.increment
    assert Watermark(store.layout).read("via-hook").consumed == (
        Watermark(store.layout).read("via-cron").consumed
    )


def test_injection_is_a_byte_prefix_of_memory_md(seeded):
    payload = injection.payload(seeded)
    raw = seeded.layout.memory_index.read_bytes()
    assert raw.startswith(payload.encode("utf-8"))
    assert len(payload.encode("utf-8")) <= seeded.config.recall.injection_budget_bytes


def test_injection_is_truncated_at_a_line_boundary_when_it_exceeds_the_budget(seeded):
    seeded.config.recall.injection_budget_bytes = len(seeded.config.memory_md.header) + len("\n\n")
    payload = injection.payload(seeded)
    assert seeded.layout.memory_index.read_bytes().startswith(payload.encode("utf-8"))
    assert "\n- " not in payload


@pytest.mark.parametrize(
    ("host", "event", "expected"),
    [
        (moments.HOST_CLAUDE_CODE, "SessionStart", moments.MOMENT_INJECT),
        (moments.HOST_CLAUDE_CODE, "PreCompact", moments.MOMENT_EVICT),
        (moments.HOST_CODEX, "session_end", moments.MOMENT_PAUSE),
        (moments.HOST_CLAUDE_CODE, "NotAThing", None),
    ],
)
def test_host_dialects_map_onto_the_universal_moments(host, event, expected):
    assert moments.moment_for(host, event) == expected


def test_hook_survives_malformed_input_without_touching_the_host_exit_code(monkeypatch, store):
    monkeypatch.setattr("sys.stdin", io.StringIO("not json at all"))
    assert hook_entry.main() == hook_entry.EXIT_OK


def test_hook_injects_memory_md_at_session_start(seeded):
    response = hook_entry.handle(
        seeded, {"host": moments.HOST_CLAUDE_CODE, "hook_event_name": "SessionStart"}
    )
    context = response[hook_entry.CLAUDE_OUTPUT_KEY][hook_entry.CLAUDE_CONTEXT_KEY]
    assert context == injection.payload(seeded)


def test_hook_at_a_boundary_returns_the_increment_and_an_instruction(store):
    response = hook_entry.handle(
        store,
        {
            "host": moments.HOST_CLAUDE_CODE,
            "hook_event_name": "Stop",
            "session_id": "hooked",
            "items": SEGMENTS,
        },
    )
    assert response["pending"] == len(SEGMENTS)
    assert SEGMENTS[-1] in response[hook_entry.CLAUDE_CONTEXT_KEY]


def test_transcript_reading_survives_a_mixed_and_partly_broken_file(tmp_path):
    path = tmp_path / "transcript.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({"type": "user", "message": {"content": [{"type": "text",
                                                                     "text": "hello"}]}}),
                "{not json",
                json.dumps({"role": "assistant", "content": "hi there"}),
            ]
        ),
        encoding="utf-8",
    )
    items = transcript.items(path)
    assert any("hello" in item for item in items)
    assert any("hi there" in item for item in items)


def test_setup_is_idempotent_and_leaves_foreign_settings_alone(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"theme": "dark"}), encoding="utf-8")

    setup.install(moments.HOST_CLAUDE_CODE, settings)
    once = json.loads(settings.read_text(encoding="utf-8"))
    setup.install(moments.HOST_CLAUDE_CODE, settings)
    twice = json.loads(settings.read_text(encoding="utf-8"))

    assert once == twice
    assert twice["theme"] == "dark"
    assert set(twice["hooks"]) == set(moments.DIALECTS[moments.HOST_CLAUDE_CODE])
