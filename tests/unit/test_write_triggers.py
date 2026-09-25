"""M4 — the watermark makes triggers optional, and hooks harmless when they misbehave."""

import io
import json

import pytest
from agent_memory.adapters import capture as capture_module
from agent_memory.adapters import hook_entry, moments, setup, transcript
from agent_memory.core import injection, sessions, triggers
from agent_memory.core.watermark import Watermark

SEGMENTS = ["user: we moved the deploy to Fridays", "assistant: noted", "user: and E4021 is fixed"]


def test_repeated_triggers_hand_over_only_the_increment(store):
    first = capture_module.capture(store, "session-a", SEGMENTS[:2])
    assert first.increment == tuple(SEGMENTS[:2])

    second = capture_module.capture(store, "session-a", SEGMENTS)
    assert second.increment == (SEGMENTS[-1],)
    assert capture_module.capture(store, "session-a", SEGMENTS).is_empty()
    assert len(sessions.read(store.layout, "session-a")) == len(SEGMENTS)


def test_a_kill_before_distillation_leaves_the_archived_tail_as_backlog(store):
    capture_module.capture(store, "session-b", SEGMENTS)
    watermark = Watermark(store.layout, store.clock)
    backlog = triggers.backlog(store.layout, "session-b", watermark)
    assert [message.text for message in backlog] == [
        segment.split(": ", 1)[1] for segment in SEGMENTS
    ]
    assert capture_module.capture(store, "session-b", SEGMENTS).is_empty()


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
    cron_state = capture_module.capture(store, "via-cron", SEGMENTS)

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
        (moments.HOST_CODEX, "Stop", moments.MOMENT_PAUSE),
        (moments.HOST_CODEX, "SessionStart", moments.MOMENT_INJECT),
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
    output = response[hook_entry.CLAUDE_OUTPUT_KEY]
    assert output[hook_entry.CLAUDE_CONTEXT_KEY] == injection.payload(seeded)
    assert output["hookEventName"] == "SessionStart"


@pytest.mark.parametrize(
    ("host", "event"),
    [
        (moments.HOST_CLAUDE_CODE, "Stop"),
        (moments.HOST_CODEX, "Stop"),
        (moments.HOST_GENERIC, moments.MOMENT_PAUSE),
    ],
)
def test_every_host_hook_archives_the_increment_and_launches_the_same_executor_call(
    store, host, event
):
    launches = []

    def launch(launched_store, session, launched_host):
        launches.append((launched_store.root, session, launched_host))
        return True

    response = hook_entry.handle(
        store,
        {
            "host": host,
            "event": event,
            "hook_event_name": event,
            "session_id": host,
            "items": SEGMENTS,
        },
        launch=launch,
    )
    assert response["pending"] == len(SEGMENTS)
    assert response[hook_entry.KEY_DISTILL] == hook_entry.DISTILL_LAUNCHED
    assert launches == [(store.root, host, host)]
    assert hook_entry.CLAUDE_CONTEXT_KEY not in response
    assert len(sessions.read(store.layout, host)) == len(SEGMENTS)


def test_the_hook_leaves_distillation_alone_when_the_boundary_switch_is_off(store):
    store.config.write.distill_on_boundary = False
    response = hook_entry.handle(
        store,
        {
            "host": moments.HOST_CLAUDE_CODE,
            "hook_event_name": "Stop",
            "session_id": "s",
            "items": SEGMENTS,
        },
        launch=lambda *_: True,
    )
    assert response[hook_entry.KEY_DISTILL] == hook_entry.DISTILL_SKIPPED


def test_transcript_reading_survives_a_mixed_and_partly_broken_file(tmp_path):
    path = tmp_path / "transcript.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    {"type": "user", "message": {"content": [{"type": "text", "text": "hello"}]}}
                ),
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


def _stop_event(store, session="s"):
    return {
        "host": moments.HOST_CLAUDE_CODE,
        "hook_event_name": "Stop",
        "session_id": session,
        "items": SEGMENTS,
        "store": str(store.root),
    }


def test_the_launched_executor_call_is_one_the_cli_accepts(store, monkeypatch):
    from agent_memory.cli.main import _parser
    from agent_memory.core.config import EXECUTOR_ENV_VAR, STORE_ENV_VAR

    launched = {}

    def fake_popen(command, **kwargs):
        launched.update(command=command, env=kwargs["env"])

    monkeypatch.setattr("subprocess.Popen", fake_popen)
    assert hook_entry.launch_distill(store, "session-x", moments.HOST_CODEX)
    args = _parser().parse_args(launched["command"][1:])
    assert args.session == ["session-x"]
    assert args.reason_host == moments.HOST_CODEX
    assert launched["env"][STORE_ENV_VAR] == str(store.root)
    assert launched["env"][EXECUTOR_ENV_VAR]


def test_a_hook_fired_inside_the_executor_session_does_nothing(store, monkeypatch, capsys):
    from agent_memory.core.config import EXECUTOR_ENV_VAR

    monkeypatch.setenv(EXECUTOR_ENV_VAR, "1")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(_stop_event(store))))
    assert hook_entry.main() == hook_entry.EXIT_OK
    assert capsys.readouterr().out == ""
    assert sessions.read(store.layout, "s") == []


def test_a_boundary_hook_prints_nothing_for_the_host_to_parse(store, monkeypatch, capsys):
    monkeypatch.setattr(hook_entry, "launch_distill", lambda *_: True)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(_stop_event(store))))
    assert hook_entry.main() == hook_entry.EXIT_OK
    assert capsys.readouterr().out == ""
    assert len(sessions.read(store.layout, "s")) == len(SEGMENTS)


def test_the_hook_takes_its_host_from_the_command_line(store, monkeypatch):
    hosts = []
    monkeypatch.setattr(hook_entry, "launch_distill", lambda s, session, host: hosts.append(host))
    event = {key: value for key, value in _stop_event(store).items() if key != "host"}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(event)))
    hook_entry.main(["--host", moments.HOST_CODEX])
    assert hosts == [moments.HOST_CODEX]


def test_codex_rollout_transcripts_yield_the_conversation(tmp_path):
    def item(payload):
        return json.dumps({"type": "response_item", "payload": payload})

    path = tmp_path / "rollout.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({"type": "session_meta", "payload": {"id": "x", "cwd": "/w"}}),
                item(
                    {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": "we deploy on Fridays"}],
                    }
                ),
                item(
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "noted"}],
                    }
                ),
                json.dumps({"type": "event_msg", "payload": {"type": "token_count"}}),
            ]
        ),
        encoding="utf-8",
    )
    assert transcript.items(path) == ["user: we deploy on Fridays", "assistant: noted"]


@pytest.mark.parametrize("host", [moments.HOST_CLAUDE_CODE, moments.HOST_CODEX])
def test_setup_writes_an_absolute_hook_command_and_installs_the_skill(tmp_path, host):
    from agent_memory.core import prompts

    settings = tmp_path / host / "hooks.json"
    setup.install(host, settings)
    hooks = json.loads(settings.read_text(encoding="utf-8"))["hooks"]
    assert set(hooks) == set(moments.DIALECTS[host])
    command = hooks["Stop"][0]["hooks"][0]["command"]
    executable = command.split()[0]
    assert executable.endswith(setup.HOOK_COMMAND) and executable.startswith("/")
    skill = settings.parent / "skills" / "agent-memory" / "SKILL.md"
    assert skill.read_text(encoding="utf-8") == prompts.skill()
