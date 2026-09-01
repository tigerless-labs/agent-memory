import ast
import pathlib

import pytest
from agent_memory.core.config import CONFIG_FILENAME, Config

CORE_SRC = pathlib.Path(__file__).resolve().parents[2] / "packages" / "core" / "src"
CONFIG_MODULE = CORE_SRC / "agent_memory" / "core" / "config.py"
LITERALS_ALLOWED_ANYWHERE = frozenset({0, 1, -1})


def test_defaults_are_complete_and_self_consistent():
    config = Config.default()

    assert config.manage.trigger_min_sessions >= 1
    assert config.manage.trigger_min_hours > 0
    assert config.manage.cluster_min_files > 1
    assert config.memory_md.budget_bytes > 0
    assert config.weight.floor < config.weight.initial < config.weight.ceiling
    assert config.weight.decay_step > 0
    assert config.weight.boost_step > 0
    assert config.recall.retrieval_weight_floor >= config.weight.floor
    assert config.recall.default_limit > 0
    assert config.recall.recency_half_life_days > 0
    assert set(config.storage.domain_types) == set(config.storage.domains)


def test_every_domain_allows_at_least_one_type_and_types_are_disjoint_from_domains():
    config = Config.default()
    for domain in config.storage.domains:
        assert config.storage.domain_types[domain]


def test_config_round_trips_through_disk(tmp_path):
    original = Config.default()
    original.manage.trigger_min_sessions += 1
    original.recall.default_limit += 1
    original.save(tmp_path)

    assert (tmp_path / CONFIG_FILENAME).exists()
    reloaded = Config.load(tmp_path)
    assert reloaded.manage.trigger_min_sessions == original.manage.trigger_min_sessions
    assert reloaded.recall.default_limit == original.recall.default_limit


def test_load_without_file_yields_defaults(tmp_path):
    assert Config.load(tmp_path).recall.default_limit == Config.default().recall.default_limit


def test_unknown_knob_is_rejected_rather_than_silently_ignored(tmp_path):
    (tmp_path / CONFIG_FILENAME).write_text("[recall]\nnot_a_knob = 3\n", encoding="utf-8")
    with pytest.raises(ValueError):
        Config.load(tmp_path)


def _numeric_literals(path: pathlib.Path) -> list[tuple[int, object]]:
    """Inline numbers are magic. A named module-level constant is not."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    named: set[int] = set()
    for statement in tree.body:
        targets = getattr(statement, "targets", [])
        if isinstance(statement, ast.Assign) and all(
            isinstance(target, ast.Name) and target.id.isupper() for target in targets
        ):
            named.update(id(node) for node in ast.walk(statement.value))

    found: list[tuple[int, object]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
            if isinstance(node.value, bool) or node.value in LITERALS_ALLOWED_ANYWHERE:
                continue
            if id(node) in named:
                continue
            found.append((node.lineno, node.value))
    return found


def test_no_magic_numbers_outside_the_config_module():
    offenders = {
        str(path.relative_to(CORE_SRC)): _numeric_literals(path)
        for path in sorted(CORE_SRC.rglob("*.py"))
        if path != CONFIG_MODULE and _numeric_literals(path)
    }
    assert offenders == {}
