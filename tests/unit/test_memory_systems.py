"""A memory system is a dialect, not a branch. Adding one must not touch the driver."""

import os
import pathlib

import pytest
from agent_memory.core import prompts
from agent_memory.core.config import Config
from agent_memory.executor import hosts
from agent_memory.harness import arms, framing, systems


@pytest.fixture
def memcore(memcore_home):
    return systems.build(systems.MEMCORE, Config.default(), memcore_home=memcore_home)


@pytest.fixture
def native():
    return systems.build(systems.NATIVE, Config.default())


def test_every_system_points_the_host_at_its_own_store(tmp_path, native, memcore, memcore_home):
    root = tmp_path / "store"
    assert native.environment(root)["AGENT_MEMORY_STORE"] == str(root)
    environment = memcore.environment(root)
    assert environment["MEMCORE_DIR"] == str(root)
    assert environment["PATH"].split(os.pathsep)[0] == str(memcore_home)


def test_memcore_speaks_through_its_own_skill_text(memcore, memcore_home):
    skill = (memcore_home / "SKILL.md").read_text(encoding="utf-8")
    for text in (memcore.experience_system_prompt(), memcore.exam_system_prompt()):
        assert skill in text
        assert text.startswith("memcore: ")
    assert memcore.discipline() == ""
    assert "memcore create" in memcore.record_hint()
    assert "memcore" in memcore.exam_preamble()
    assert "mem context" not in memcore.exam_preamble()


def test_native_keeps_its_own_discipline_and_hints(native):
    assert native.discipline() == prompts.WRITE_DISCIPLINE
    assert "mem record" in native.record_hint()
    assert "mem context" in native.exam_preamble()
    assert native.experience_system_prompt().startswith(prompts.MEMORY_KEEPER)


def test_the_synthesis_hint_is_a_config_knob_visible_to_the_fingerprint():
    on, off = Config.default(), Config.default()
    off.recall.synthesis_hint = False
    with_hint = systems.build(systems.NATIVE, on)
    without = systems.build(systems.NATIVE, off)
    assert len(with_hint.exam_preamble()) > len(without.exam_preamble())
    assert with_hint.fingerprint() != without.fingerprint()


def test_the_experience_prompt_shares_the_task_and_swaps_only_the_systems_part(native, memcore):
    segment = "user: my sister gave me a snake plant"
    ours = framing.experience(
        arms.MODE_BOUNDARY, segment, native.record_hint(), native.discipline()
    )
    theirs = framing.experience(
        arms.MODE_BOUNDARY, segment, memcore.record_hint(), memcore.discipline()
    )
    assert segment in ours and segment in theirs
    assert framing.BOUNDARY in ours and framing.BOUNDARY in theirs
    assert native.discipline() in ours and native.discipline() not in theirs
    assert memcore.record_hint() in theirs and native.record_hint() in ours
    shared = ours.replace(native.discipline(), "").replace(native.record_hint(), "")
    assert shared.split() == theirs.replace(memcore.record_hint(), "").split()


def test_the_exam_prompt_takes_the_systems_preamble(native, memcore):
    from agent_memory.harness import dataset

    episode = dataset.Episode(
        id="q1", question="What plant?", answer="snake plant", question_type="t",
        question_date="2026/02/01", sessions=(), evidence_session_ids=(),
    )
    ours = framing.exam(episode, native.exam_preamble())
    theirs = framing.exam(episode, memcore.exam_preamble())
    assert episode.question in ours and episode.question in theirs
    assert "mem context" in ours and "memcore recall" in theirs
    assert "memcore" not in framing.exam(episode, "")


def test_memcore_prepare_initialises_a_store_with_the_model_linked_in(
    tmp_path, memcore, memcore_home
):
    root = tmp_path / "stores" / "W2" / "q1"
    memcore.prepare(root, fresh=True)
    assert (root / "memories").is_dir()
    assert (root / "models").is_symlink()
    assert (root / "models").resolve() == (memcore_home / "models").resolve()


def test_memcore_reopens_an_existing_store_and_refuses_a_missing_one(tmp_path, memcore):
    root = tmp_path / "q1"
    memcore.prepare(root, fresh=True)
    memcore.prepare(root, fresh=False)
    with pytest.raises(FileNotFoundError):
        memcore.prepare(tmp_path / "nothing", fresh=False)


def test_memcore_counts_and_reads_the_nodes_it_holds(tmp_path, memcore):
    root = tmp_path / "q1"
    memcore.prepare(root, fresh=True)
    assert memcore.record_count(root) == 0
    (root / "memories" / "snake plant.md").write_text("---\nabstract: a\n---\nsnake", "utf-8")
    (root / "memories" / "oat milk.md").write_text("---\nabstract: b\n---\noat", "utf-8")
    assert memcore.record_count(root) == 2
    assert sorted(memcore.record_texts(root)) == sorted(
        ["---\nabstract: a\n---\nsnake", "---\nabstract: b\n---\noat"]
    )


def test_memcore_release_stops_its_daemon(tmp_path, memcore):
    root = tmp_path / "q1"
    memcore.prepare(root, fresh=True)
    memcore.release(root)
    assert (root / "calls.log").read_text(encoding="utf-8").strip().splitlines()[-1] == "stop"


def test_memcore_injection_is_what_its_hook_injects(tmp_path, memcore):
    root = tmp_path / "q1"
    memcore.prepare(root, fresh=True)
    assert memcore.injection(root) == ""
    (root / "memories" / "snake plant gift.md").write_text("---\nabstract: a\n---\n", "utf-8")
    injected = memcore.injection(root)
    assert "snake plant gift" in injected
    assert "memcore recall --top-k" in injected


def test_memcore_keeps_no_transcript(tmp_path, memcore):
    root = tmp_path / "q1"
    memcore.prepare(root, fresh=True)
    memcore.archive(root, "q1-0", "user: secret transcript")
    files = [path for path in root.rglob("*") if path.is_file()]
    assert not any("secret transcript" in path.read_text("utf-8") for path in files)


def test_the_native_system_archives_the_transcript(tmp_path, native):
    from agent_memory.core.store import Store

    root = tmp_path / "q1"
    native.prepare(root, fresh=True)
    native.archive(root, "q1-0", "user: the drain window rule")
    archived = list(Store(root).layout.sessions.glob("*.txt"))
    assert archived and "drain window" in archived[0].read_text(encoding="utf-8")


def test_each_system_has_its_own_fingerprint_so_attribution_is_refused_across_them(
    tmp_path, native, memcore, memcore_home
):
    assert native.fingerprint() == Config.default().recall_fingerprint()
    assert memcore.fingerprint() != native.fingerprint()
    again = systems.build(systems.MEMCORE, Config.default(), memcore_home=memcore_home)
    assert again.fingerprint() == memcore.fingerprint()
    skill = (memcore_home / "SKILL.md").read_text(encoding="utf-8")
    (memcore_home / "SKILL.md").write_text(skill + "\nmore", encoding="utf-8")
    changed = systems.build(systems.MEMCORE, Config.default(), memcore_home=memcore_home)
    assert changed.fingerprint() != memcore.fingerprint()


def test_the_claude_dialect_allows_only_the_systems_own_command(tmp_path, memcore):
    command = hosts.DIALECTS[hosts.HOST_CLAUDE_CODE].command(
        hosts.HostSpec(name=hosts.HOST_CLAUDE_CODE, binary="claude", model="m"),
        tools_enabled=True,
        system_prompt="s",
        max_turns=5,
        store_root=tmp_path,
        answer_file=tmp_path / "a.txt",
        tool_pattern=memcore.tool_pattern,
    )
    allowed = command[command.index("--allowedTools") + 1]
    assert allowed == memcore.tool_pattern
    assert "mem:" not in allowed


def test_a_system_is_chosen_by_name_and_unknown_names_are_refused(memcore_home):
    assert systems.build(systems.NATIVE, Config.default()).name == systems.NATIVE
    built = systems.build(systems.MEMCORE, Config.default(), memcore_home=memcore_home)
    assert built.name == systems.MEMCORE
    with pytest.raises(ValueError):
        systems.build("nope", Config.default())


def test_memcore_without_a_home_is_an_error_naming_the_variable(monkeypatch):
    monkeypatch.delenv(systems.MEMCORE_HOME_ENV, raising=False)
    with pytest.raises(ValueError, match=systems.MEMCORE_HOME_ENV):
        systems.build(systems.MEMCORE, Config.default())


def test_memcore_finds_its_binary_in_either_layout(tmp_path, memcore_home):
    released = systems.build(systems.MEMCORE, Config.default(), memcore_home=memcore_home)
    assert released.binary == memcore_home / "memcore"
    built = tmp_path / "checkout"
    (built / "target" / "release").mkdir(parents=True)
    (built / "target" / "release" / "memcore").write_text("", encoding="utf-8")
    (built / "SKILL.md").write_text("skill", encoding="utf-8")
    (built / "models").mkdir()
    from_source = systems.build(systems.MEMCORE, Config.default(), memcore_home=built)
    assert from_source.binary == built / "target" / "release" / "memcore"


def test_the_fixed_exam_is_native_only(tmp_path, native, memcore):
    assert native.supports_fixed_exam
    assert not memcore.supports_fixed_exam
    with pytest.raises(NotImplementedError):
        memcore.context(tmp_path, "what plant?")


def test_paths_are_data_not_defaults():
    """No machine-specific path is baked in; the checkout comes from the environment."""
    import inspect

    source = inspect.getsource(systems)
    assert "/home/" not in source
    assert pathlib.Path.home().name not in source
