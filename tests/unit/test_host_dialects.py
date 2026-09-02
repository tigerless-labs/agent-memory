"""P1 — a host is a dialect, not a branch. Adding one must not touch the driver."""

import pytest
from agent_memory.harness import hosts


def _spec(name):
    return hosts.HostSpec(name=name, binary=name, model="a-model")


@pytest.mark.parametrize("name", hosts.DIALECTS)
def test_every_dialect_builds_a_command_that_starts_with_its_binary(name, tmp_path):
    dialect = hosts.DIALECTS[name]
    command = dialect.command(
        _spec(name),
        tools_enabled=True,
        system_prompt="be a memory keeper",
        max_turns=10,
        store_root=tmp_path / "store",
        answer_file=tmp_path / "answer.txt",
    )
    assert command[0] == name
    assert "a-model" in command


@pytest.mark.parametrize("name", hosts.DIALECTS)
def test_the_system_prompt_reaches_the_host_one_way_or_the_other(name, tmp_path):
    dialect = hosts.DIALECTS[name]
    system = "you are a memory keeper"
    command = dialect.command(
        _spec(name),
        tools_enabled=True,
        system_prompt=system,
        max_turns=10,
        store_root=tmp_path / "store",
        answer_file=tmp_path / "answer.txt",
    )
    delivered = dialect.stdin("the question", system)
    assert system in " ".join(command) or system in (delivered or "")


@pytest.mark.parametrize("name", hosts.DIALECTS)
def test_no_dialect_leaves_its_own_memory_layer_running(name, tmp_path):
    """Two memory systems in one run make the score unattributable."""
    dialect = hosts.DIALECTS[name]
    command = " ".join(
        dialect.command(
            _spec(name),
            tools_enabled=True,
            system_prompt="s",
            max_turns=10,
            store_root=tmp_path / "store",
            answer_file=tmp_path / "answer.txt",
        )
    )
    assert dialect.disables_native_memory(command)


def test_claude_code_delivers_the_system_prompt_by_flag(tmp_path):
    command = hosts.DIALECTS[hosts.HOST_CLAUDE_CODE].command(
        _spec(hosts.HOST_CLAUDE_CODE),
        tools_enabled=True,
        system_prompt="keeper",
        max_turns=7,
        store_root=tmp_path / "store",
        answer_file=tmp_path / "answer.txt",
    )
    assert "--system-prompt" in command
    assert "keeper" in command


def test_codex_is_given_write_access_to_the_store_it_must_reach(tmp_path):
    store = tmp_path / "store"
    command = hosts.DIALECTS[hosts.HOST_CODEX].command(
        _spec(hosts.HOST_CODEX),
        tools_enabled=True,
        system_prompt="keeper",
        max_turns=7,
        store_root=store,
        answer_file=tmp_path / "answer.txt",
    )
    assert "--add-dir" in command
    assert str(store) in command
    assert "workspace-write" in command


def test_codex_without_tools_stays_read_only(tmp_path):
    command = hosts.DIALECTS[hosts.HOST_CODEX].command(
        _spec(hosts.HOST_CODEX),
        tools_enabled=False,
        system_prompt="",
        max_turns=7,
        store_root=None,
        answer_file=tmp_path / "answer.txt",
    )
    assert "read-only" in command
    assert "--add-dir" not in command


def test_hermes_enables_only_the_toolset_that_reaches_the_mem_cli(tmp_path):
    command = hosts.DIALECTS[hosts.HOST_HERMES].command(
        _spec(hosts.HOST_HERMES),
        tools_enabled=True,
        system_prompt="keeper",
        max_turns=7,
        store_root=tmp_path / "store",
        answer_file=tmp_path / "answer.txt",
    )
    toolsets = command[command.index("-t") + 1].split(",")
    assert "terminal" in toolsets
    assert "memory" not in toolsets


def test_codex_reads_its_answer_from_the_file_not_the_transcript(tmp_path):
    answer_file = tmp_path / "answer.txt"
    answer_file.write_text("the final answer\n", encoding="utf-8")
    noisy = (
        "sandbox: read-only\nsession id: abc\nuser\nquestion\n"
        "codex\nthe final answer\ntokens used"
    )
    assert hosts.DIALECTS[hosts.HOST_CODEX].answer(noisy, answer_file) == "the final answer"


def test_stdout_hosts_return_stdout(tmp_path):
    for name in (hosts.HOST_CLAUDE_CODE, hosts.HOST_HERMES):
        dialect = hosts.DIALECTS[name]
        assert dialect.answer("  the answer  ", tmp_path / "missing.txt") == "the answer"


def test_an_unavailable_host_is_reported_rather_than_silently_skipped():
    spec = hosts.HostSpec(name="nope", binary="definitely-not-installed", model="m")
    assert not spec.available()


def test_hermes_re_adds_the_prefix_it_is_about_to_strip(tmp_path):
    """It consumes one provider prefix as routing; a publisher-qualified backend needs it back."""
    spec = hosts.HostSpec(
        name=hosts.HOST_HERMES, binary="hermes", model="google/gemini-3.7-flash",
        provider="gemini",
    )
    command = hosts.DIALECTS[hosts.HOST_HERMES].command(
        spec, tools_enabled=True, system_prompt="k", max_turns=7,
        store_root=tmp_path / "store", answer_file=tmp_path / "a.txt",
    )
    assert command[command.index("--model") + 1] == "gemini/google/gemini-3.7-flash"


def test_hermes_leaves_the_model_alone_when_no_provider_is_pinned(tmp_path):
    spec = hosts.HostSpec(name=hosts.HOST_HERMES, binary="hermes", model="some-model")
    command = hosts.DIALECTS[hosts.HOST_HERMES].command(
        spec, tools_enabled=True, system_prompt="k", max_turns=7,
        store_root=None, answer_file=tmp_path / "a.txt",
    )
    assert command[command.index("--model") + 1] == "some-model"


def test_the_expensive_tier_has_to_be_asked_for_out_loud(monkeypatch):
    """A matrix is hundreds of calls; the costly model must not arrive by default or typo."""
    from agent_memory.harness.main import ALLOW_COSTLY_ENV, _affordable

    monkeypatch.delenv(ALLOW_COSTLY_ENV, raising=False)
    with pytest.raises(ValueError, match="expensive tier"):
        _affordable("claude-opus-5", "judge")
    with pytest.raises(ValueError):
        _affordable("CLAUDE-OPUS-4-8", "claude-code")

    assert _affordable("claude-haiku-4-5-20251001", "claude-code")
    assert _affordable("claude-sonnet-5", "judge")

    monkeypatch.setenv(ALLOW_COSTLY_ENV, "1")
    assert _affordable("claude-opus-5", "judge") == "claude-opus-5"


def test_the_shipped_defaults_are_all_affordable(monkeypatch):
    from agent_memory.harness.main import (
        ALLOW_COSTLY_ENV,
        HOST_BINARIES,
        JUDGE_MODEL,
        _affordable,
    )

    monkeypatch.delenv(ALLOW_COSTLY_ENV, raising=False)
    _affordable(JUDGE_MODEL, "judge")
    for name, (_, model) in HOST_BINARIES.items():
        _affordable(model, name)
