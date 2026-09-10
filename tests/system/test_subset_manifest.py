"""Offline preparation checks: no driver, model, Judge or Store writes."""

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "subset_prepare", ROOT / "experiments/subsets/prepare.py"
)
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


def test_frozen_manifest_matches_sources(monkeypatch):
    expected = json.loads(prepare.DEFAULT.read_text())
    # main no longer tracks the corpus; retain the original frozen truth selection.
    check_output = prepare.subprocess.check_output

    def frozen_paths(command, **kwargs):
        if command[:2] == ["git", "ls-files"]:
            command = ["git", "ls-tree", "-r", "--name-only", "-z",
                       expected["preparation_code_revision"], "--", prepare.CORPUS]
        return check_output(command, **kwargs)

    monkeypatch.setattr(prepare.subprocess, "check_output", frozen_paths)
    actual = prepare.build()
    # Code provenance belongs to the original experiment, while current sampling
    # and parsing must still reproduce its data and selected IDs exactly.
    for path, digest in expected["preparation_source_sha256"].items():
        if actual["preparation_source_sha256"][path] == digest:
            continue
        historical = check_output(
            ["git", "show", f'{expected["preparation_code_revision"]}:{path}'], cwd=ROOT,
        )
        assert hashlib.sha256(historical).hexdigest() == digest
    actual["preparation_source_sha256"] = expected["preparation_source_sha256"]
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
