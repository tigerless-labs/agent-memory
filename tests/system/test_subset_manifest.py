"""Offline preparation checks: no driver, model, Judge or Store writes."""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "subset_prepare", ROOT / "experiments/subsets/prepare.py"
)
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


def test_frozen_manifest_matches_sources():
    expected = json.loads(prepare.DEFAULT.read_text())
    actual = prepare.build()
    actual["preparation_code_revision"] = expected["preparation_code_revision"]
    actual.pop("manifest_sha256")
    actual["manifest_sha256"] = prepare.digest(actual)
    assert actual == expected


def test_nested_prefixes_and_source_order_independence():
    episodes = prepare.dataset.load(ROOT / prepare.SUITE)
    frozen = prepare.sampling.stratified(episodes, 20, prepare.SEED)
    manifest = json.loads(prepare.DEFAULT.read_text())
    previous = []
    for stage in manifest["stages"]:
        selected = prepare.sampling.stratified(frozen, stage["per_type"], prepare.SEED)
        reverse = prepare.sampling.stratified(
            list(reversed(frozen)), stage["per_type"], prepare.SEED
        )
        assert selected == reverse
        assert {e.id for e in selected} == set(stage["cumulative_question_ids"])
        assert stage["cumulative_question_ids"] == previous + stage["added_question_ids"]
        assert not set(previous) & set(stage["added_question_ids"])
        assert len(set(stage["cumulative_question_ids"])) == stage["total"]
        for kind, order in manifest["bucket_orders"].items():
            assert {e.id for e in selected if e.question_type == kind} == set(
                order[: stage["per_type"]]
            )
        previous = stage["cumulative_question_ids"]
