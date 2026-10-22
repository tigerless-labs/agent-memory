import ast
import pathlib

import pytest
from agent_memory.core.config import (
    CONFIG_FILENAME,
    REASONER_HOST,
    TOOL_MODE_AUTO,
    TOOL_MODE_NATIVE,
    Config,
)

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
    assert config.manage.review_max_steps > 0
    assert config.manage.review_max_tool_calls >= config.manage.review_max_steps
    assert config.manage.review_tool_result_chars > 0
    assert config.manage.review_evidence_chars >= config.manage.review_tool_result_chars
    assert config.manage.review_raw_session_evidence is False
    assert config.recall.default_limit > 0
    assert config.recall.recency_half_life_days > 0
    assert config.storage.max_depth >= len(("type", "file"))
    assert config.executor.reasoner == REASONER_HOST
    assert config.executor.project == ""
    assert config.executor.host_provider == ""
    assert config.executor.host_allow_data_training is False
    assert config.executor.tool_mode == TOOL_MODE_AUTO
    assert config.executor.write.reasoner == ""
    assert config.executor.write.host == ""
    assert config.executor.write.tool_mode == ""
    assert config.executor.manage.reasoner == ""
    assert config.executor.manage.host == ""


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
    original.index.vector_enabled = True
    original.index.vector_model = "test/model-v2"
    original.executor.write.reasoner = "host"
    original.executor.write.host = "muse-code"
    original.executor.write.host_provider = "openrouter"
    original.executor.write.host_allow_data_training = True
    original.executor.write.tool_mode = TOOL_MODE_NATIVE
    original.executor.manage.reasoner = "endpoint"
    original.executor.manage.project = "user-project"
    original.manage.review_raw_session_evidence = True
    original.save(tmp_path)

    assert (tmp_path / CONFIG_FILENAME).exists()
    reloaded = Config.load(tmp_path)
    assert reloaded.manage.trigger_min_sessions == original.manage.trigger_min_sessions
    assert reloaded.recall.default_limit == original.recall.default_limit
    assert reloaded.index.vector_enabled is True
    assert reloaded.index.vector_model == "test/model-v2"
    assert reloaded.executor.write.host == "muse-code"
    assert reloaded.executor.write.host_provider == "openrouter"
    assert reloaded.executor.write.host_allow_data_training is True
    assert reloaded.executor.write.tool_mode == TOOL_MODE_NATIVE
    assert reloaded.executor.manage.reasoner == "endpoint"
    assert reloaded.executor.manage.project == "user-project"
    assert reloaded.manage.review_raw_session_evidence is True


def test_legacy_flat_executor_config_remains_valid(tmp_path):
    (tmp_path / CONFIG_FILENAME).write_text(
        """[executor]
reasoner = "endpoint"
project = "user-project"
model = "google/gemini-test"
""",
        encoding="utf-8",
    )

    loaded = Config.load(tmp_path)

    assert loaded.executor.reasoner == "endpoint"
    assert loaded.executor.project == "user-project"
    assert loaded.executor.write.reasoner == ""
    assert loaded.executor.manage.reasoner == ""


def test_nested_operation_executor_config_loads_without_replacing_legacy_fallbacks(tmp_path):
    (tmp_path / CONFIG_FILENAME).write_text(
        """[executor]
reasoner = "host"
host = "codex"

[executor.write]
reasoner = "host"
host = "source"

[executor.manage]
reasoner = "endpoint"
endpoint = "https://models.example/v1"
model = "gemini-test"
""",
        encoding="utf-8",
    )

    loaded = Config.load(tmp_path)

    assert loaded.executor.host == "codex"
    assert loaded.executor.write.host == "source"
    assert loaded.executor.manage.reasoner == "endpoint"
    assert loaded.executor.manage.endpoint == "https://models.example/v1"


def test_vector_knobs_leave_the_recall_fingerprint_alone_while_disabled():
    config = Config.default()
    before = config.recall_fingerprint()
    config.index.vector_model = "test/another-model"
    assert config.recall_fingerprint() == before


def test_default_recall_fingerprint_matches_memory_only_policy():
    assert Config.default().recall_fingerprint() == "a8f591edf4e3b73b"


def test_enabling_vector_changes_the_recall_fingerprint_and_so_does_the_model():
    config = Config.default()
    before = config.recall_fingerprint()
    config.index.vector_enabled = True
    enabled = config.recall_fingerprint()
    assert enabled != before
    config.index.vector_model = "test/another-model"
    assert config.recall_fingerprint() != enabled


def test_load_without_file_yields_defaults(tmp_path):
    assert Config.load(tmp_path).recall.default_limit == Config.default().recall.default_limit


def test_unknown_knob_is_rejected_rather_than_silently_ignored(tmp_path):
    (tmp_path / CONFIG_FILENAME).write_text("[recall]\nnot_a_knob = 3\n", encoding="utf-8")
    with pytest.raises(ValueError):
        Config.load(tmp_path)


@pytest.mark.parametrize(
    "value, error",
    [("'true'", "index.vector_enabled"), ("''", "index.vector_model")],
)
def test_invalid_vector_configuration_is_rejected(tmp_path, value, error):
    knob = "vector_enabled" if "enabled" in error else "vector_model"
    (tmp_path / CONFIG_FILENAME).write_text(f"[index]\n{knob} = {value}\n", encoding="utf-8")
    with pytest.raises(ValueError, match=error):
        Config.load(tmp_path)


def test_non_boolean_raw_session_review_permission_is_rejected(tmp_path):
    (tmp_path / CONFIG_FILENAME).write_text(
        '[manage]\nreview_raw_session_evidence = "true"\n', encoding="utf-8"
    )
    with pytest.raises(ValueError, match="manage.review_raw_session_evidence"):
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


@pytest.mark.parametrize(
    "section, knob, literal",
    [
        ("manage", "auto_dream", '"false"'),
        ("manage", "trigger_min_sessions", '"3"'),
        ("manage", "trigger_min_sessions", "true"),
        ("manage", "claim_lease_seconds", '"1800"'),
        ("recall", "default_limit", "2.5"),
        ("storage", "default_group", "7"),
    ],
)
def test_a_knob_of_the_wrong_type_is_rejected_rather_than_stored(tmp_path, section, knob, literal):
    (tmp_path / CONFIG_FILENAME).write_text(f"[{section}]\n{knob} = {literal}\n", encoding="utf-8")
    with pytest.raises(ValueError, match=f"{section}.{knob}"):
        Config.load(tmp_path)


def test_a_whole_number_is_a_valid_value_for_a_decimal_knob(tmp_path):
    (tmp_path / CONFIG_FILENAME).write_text(
        "[manage]\nclaim_lease_seconds = 60\n", encoding="utf-8"
    )
    assert Config.load(tmp_path).manage.claim_lease_seconds == 60
