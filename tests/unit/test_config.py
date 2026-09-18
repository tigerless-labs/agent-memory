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
    assert config.manage.max_merges_per_sleep >= 0
    assert config.recall.default_limit > 0
    assert config.recall.recency_half_life_days > 0
    assert config.storage.max_depth >= len(("type", "file"))


def test_every_factory_group_field_has_a_source_that_may_name_a_directory():
    from agent_memory.core import schema

    config = Config.default()
    for item in schema.FACTORY:
        if item.group:
            source = schema.source_of(item.group, config)
            assert source in (schema.SOURCE_SYSTEM, schema.SOURCE_MENU)


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
def test_adaptive_read_config_round_trip_and_fingerprint(tmp_path):
    from agent_memory.core.config import Config

    enabled = Config.default()
    disabled = Config.default()
    disabled.recall.adaptive_read_enabled = False
    assert enabled.recall_fingerprint() != disabled.recall_fingerprint()
    enabled.save(tmp_path)
    assert Config.load(tmp_path).recall.adaptive_read_enabled
    assert Config.load(tmp_path).recall.max_recall_rounds == 2
    assert Config.load(tmp_path).recall.max_full_reads == 4


def test_adaptive_read_rejects_invalid_budgets_and_switch(tmp_path):
    from agent_memory.core.config import Config

    config = Config.default()
    for field, value in (("max_recall_rounds", 0), ("max_full_reads", -1),
                         ("adaptive_read_enabled", "yes")):
        config.save(tmp_path)
        path = tmp_path / "config.toml"
        old = repr(getattr(config.recall, field)).replace("True", "true")
        path.write_text(
            path.read_text().replace(f"{field} = {old}", f"{field} = {value!r}"),
            encoding="utf-8",
        )
        import pytest
        with pytest.raises(ValueError, match=field):
            Config.load(tmp_path)


def test_runner_refuses_unbounded_adaptive_policy():
    import pytest
    from agent_memory.harness.main import _configured

    with pytest.raises(ValueError, match="max_recall_rounds"):
        _configured(["recall.max_recall_rounds=3"])
