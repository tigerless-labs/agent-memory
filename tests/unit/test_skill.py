"""The skill file is a rendering of the prompt module, never a second copy of the discipline."""

import pathlib

import pytest
from agent_memory.cli.main import main
from agent_memory.core import prompts

SKILL_PATH = pathlib.Path(__file__).resolve().parents[2] / "skills" / "agent-memory" / "SKILL.md"


def test_the_checked_in_skill_is_what_the_prompt_module_renders():
    assert SKILL_PATH.read_text(encoding="utf-8") == prompts.skill()


def test_the_skill_carries_the_same_discipline_the_executor_is_given():
    assert prompts.WRITE_DISCIPLINE in prompts.skill()


def test_the_skill_command_prints_the_rendering(tmp_path, capsys):
    root = tmp_path / "store"
    assert main(["--store", str(root), "init"]) == 0
    capsys.readouterr()
    assert main(["--store", str(root), "skill"]) == 0
    assert capsys.readouterr().out.strip() == prompts.skill().strip()


def test_default_read_prompts_include_the_authoritative_evidence_policy():
    for text in (prompts.exam("mem recall <query>"), prompts.skill()):
        assert text.count(prompts.EVIDENCE_SUFFICIENCY_HINT) == 1


@pytest.mark.parametrize("synthesis", [False, True])
@pytest.mark.parametrize("evidence_sufficiency", [False, True])
def test_read_hints_are_independent_and_preserve_the_original_preamble(
    synthesis, evidence_sufficiency
):
    hint = "mem recall <query>"
    text = prompts.exam(hint, synthesis=synthesis, evidence_sufficiency=evidence_sufficiency)
    assert (prompts.SYNTHESIS_HINT in text) is synthesis
    assert (prompts.EVIDENCE_SUFFICIENCY_HINT in text) is evidence_sufficiency
    expected = prompts.EXAM_PREAMBLE.format(recall_hint=hint)
    if synthesis:
        expected += "\n\n" + prompts.SYNTHESIS_HINT
    if evidence_sufficiency:
        expected += "\n\n" + prompts.EVIDENCE_SUFFICIENCY_HINT
    assert text == expected


def test_adaptive_policy_has_single_source_and_bounded_fact_level_loop():
    policy = prompts.ADAPTIVE_READ_POLICY.format(max_recall_rounds=2, max_full_reads=4)
    for rendered in (prompts.exam("mem recall <query>", adaptive_read=True), prompts.skill()):
        assert rendered.count(policy) == 1
        for fragment in ("prior", "self-contained", "missing", "--round follow-up", "full"):
            assert fragment in rendered


def test_master_off_recovers_mainline_exam_and_skill_without_evidence_gate():
    hint = "mem recall <query>"
    assert prompts.exam(hint, adaptive_read=False, evidence_sufficiency=False) == (
        prompts.EXAM_PREAMBLE.format(recall_hint=hint) + "\n\n" + prompts.SYNTHESIS_HINT
    )
    assert prompts.EVIDENCE_SUFFICIENCY_HINT not in prompts.skill(adaptive_read=False)
    assert "--round follow-up" not in prompts.skill(adaptive_read=False)
