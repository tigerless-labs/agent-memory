"""The write-coverage probe: did the answer reach disk at all? Deterministic, offline."""

import json

import pytest
from agent_memory.core.config import Config
from agent_memory.core.store import Store
from agent_memory.harness import coverage, systems
from agent_memory.harness.metrics import STATUS_OK, MetricsSink, RunRecord

GOLD = "a snake plant from her sister in March"


def test_cover_is_lexical_and_thresholded():
    assert coverage.covers("She got a snake plant from her sister in March", GOLD)
    assert not coverage.covers("Prefers oat milk in coffee", GOLD)
    assert not coverage.covers("anything", "")
    assert coverage.covers("snake plant sister", GOLD, threshold=0.6)
    assert not coverage.covers("snake plant sister", GOLD, threshold=1.0)


def _record(arm, episode_id, system, expected=GOLD, memories=1):
    return RunRecord(
        run_id="r",
        arm=arm,
        host="stub",
        episode_id=episode_id,
        question_type="t",
        status=STATUS_OK,
        correct=False,
        answer="",
        expected=expected,
        memories_written=memories,
        experience_calls=1,
        experience_seconds=1.0,
        blocking_seconds=0.0,
        exam_seconds=1.0,
        judge_seconds=1.0,
        recall_fingerprint="f",
        episode_fingerprint="e",
        system=system,
    )


@pytest.fixture
def workspace(tmp_path):
    stores = tmp_path / "stores"
    native = systems.build(systems.NATIVE, Config.default())
    covered = stores / "W2" / "q1"
    native.prepare(covered, fresh=True)
    Store(covered).record(
        type="fact",
        abstract="Sister gave a snake plant on 2023-03-04",
        body="A snake plant from her sister.",
    )
    missed = stores / "W2" / "q2"
    native.prepare(missed, fresh=True)
    Store(missed).record(type="preference", abstract="Prefers oat milk")
    abstention = stores / "W2" / "q3_abs"
    native.prepare(abstention, fresh=True)

    memcore_root = stores / "W2" / "q4"
    (memcore_root / "memories").mkdir(parents=True)
    (memcore_root / "memories" / "plant.md").write_text(
        "---\nabstract: snake plant from sister\n---\nbody", encoding="utf-8"
    )

    sink = MetricsSink(tmp_path)
    sink.append(_record("W2", "q1", systems.NATIVE))
    sink.append(_record("W2", "q2", systems.NATIVE))
    sink.append(_record("W2", "q3_abs", systems.NATIVE, expected="not enough information"))
    sink.append(_record("W0", "q1", systems.NATIVE, memories=0))
    sink.append(_record("W2", "q4", systems.MEMCORE))
    return tmp_path


def test_probe_counts_answerable_episodes_whose_answer_reached_a_record(workspace):
    rows = coverage.probe(MetricsSink(workspace).records(), workspace / "stores")
    by_key = {(row.system, row.arm): row for row in rows}
    assert by_key[(systems.NATIVE, "W2")].answerable == 2
    assert by_key[(systems.NATIVE, "W2")].covered == 1
    assert by_key[(systems.MEMCORE, "W2")].answerable == 1
    assert by_key[(systems.MEMCORE, "W2")].covered == 1
    assert (systems.NATIVE, "W0") not in by_key


def test_probe_reads_records_without_a_system_field_as_native(workspace):
    records = MetricsSink(workspace).records()
    for record in records:
        record.pop("system", None)
    rows = coverage.probe(records, workspace / "stores")
    assert {row.system for row in rows} == {systems.NATIVE}


def test_probe_renders_one_line_per_system_and_arm(workspace):
    rows = coverage.probe(MetricsSink(workspace).records(), workspace / "stores")
    text = coverage.render(rows)
    assert systems.NATIVE in text and systems.MEMCORE in text
    assert "1/2" in text and "1/1" in text
    assert json.loads(coverage.as_json(rows))[0]["covered"] in (0, 1)
