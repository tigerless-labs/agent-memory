"""The skill file is a rendering of the prompt module, never a second copy of the discipline."""

import pathlib

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
