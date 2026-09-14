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
