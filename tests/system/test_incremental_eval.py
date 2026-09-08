"""Exercise the real CLI/Driver/JSONL/aggregation with fake transport and tiny Stores."""

import dataclasses
import json
from pathlib import Path

import pytest
from agent_memory.core.config import Config
from agent_memory.core.recall import Recall
from agent_memory.core.store import Store
from agent_memory.executor.hosts import Host, HostResult, HostSpec
from agent_memory.harness import dataset, incremental, main


class FakeHost(Host):
    def __init__(self, name="tested", model="fake-model"):
        super().__init__(HostSpec(name=name, binary="fake", model=model))
        self.calls = []
        self.fail = set()
        self.interrupt_at = None
        self.observed_configs = []
        self.observed_hits = []

    def run(self, prompt, **kwargs):
        if self.interrupt_at == len(self.calls):
            raise RuntimeError("interrupted transport")
        self.calls.append(prompt)
        if kwargs.get("store_root"):
            self.observed_configs.append(Config.load(kwargs["store_root"]).recall.default_limit)
            self.observed_hits.extend(
                hit.name for hit in Recall(Store(kwargs["store_root"])).recall("fixture memory")
            )
        if any(q in prompt for q in self.fail):
            return HostResult("", False, 0, "fake failure")
        return HostResult("yes", True, 0)


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[2]
    raw = json.loads((root / "experiments/subsets/p4sup-seed20260901.json").read_text())
    entries, stores, truth = [], {}, {}
    source = tmp_path / "source"
    for kind, order in raw["bucket_orders"].items():
        for q in order:
            entries.append(
                {
                    "question_id": q,
                    "question_type": kind,
                    "question": f"Question: {q}",
                    "answer": "yes",
                    "haystack_session_ids": [],
                    "haystack_dates": [],
                    "haystack_sessions": [],
                }
            )
            folder = source / "W2" / q
            store = Store(folder)
            store.init()
            if len(entries) == 1:
                store.record(
                    name="fixture-memory",
                    abstract="fixture memory for retrieval",
                    type="fact",
                    domain="user",
                    body="offline fixture fact",
                )
            files = {
                p.relative_to(folder).as_posix(): incremental.file_hash(p)
                for p in folder.rglob("*")
                if p.is_file() and ".index" not in p.parts
            }
            stores[q] = {"files": files, "truth_sha256": incremental.digest(files)}
            truth.update({f"W2/{q}/{p}": h for p, h in files.items()})
    suite = tmp_path / "suite.json"
    suite.write_text(json.dumps(entries))
    raw["source_suite"]["sha256"] = incremental.file_hash(suite)
    raw["episode_content_sha256"] = {
        e.id: incremental.digest(dataclasses.asdict(e)) for e in dataset.load(suite)
    }
    raw["source_store_corpus"].update(stores=stores, truth_sha256=incremental.digest(truth))
    raw.pop("manifest_sha256")
    raw["manifest_sha256"] = incremental.digest(raw)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(raw))
    host, judge = FakeHost(), FakeHost("judge")
    monkeypatch.setattr(main, "_host", lambda name, model="", **kw: host)
    monkeypatch.setattr(main, "_judge_host", lambda name, model="": judge)
    monkeypatch.setattr(main, "_available", lambda *args: True)
    return manifest, suite, source, host, judge


def command(fixture, workspace, stage, arm="baseline", extra=()):
    manifest, suite, source, _, _ = fixture
    return [
        "run",
        "--suite",
        str(suite),
        "--subset-manifest",
        str(manifest),
        "--reuse-stores",
        str(source),
        "--workspace",
        str(workspace),
        "--arms",
        "W2",
        "--experiment-version",
        "read-v1-replay1",
        "--experiment-arm",
        arm,
        "--stage",
        str(stage),
        "--concurrency",
        "1",
        *extra,
    ]


def test_expand_repeat_and_cumulative_reports(fixture, tmp_path, capsys):
    workspace = tmp_path / "results"
    host, judge = fixture[3:]
    for total, added in ((12, 12), (24, 12), (48, 24), (96, 48), (120, 24)):
        before = len(host.calls)
        assert main.main(command(fixture, workspace, total)) == 0
        assert len(host.calls) - before == added
        assert (
            main.main(command(fixture, workspace, total, extra=("--run-id", "new-invocation"))) == 0
        )
        assert len(host.calls) == total
        assert len(judge.calls) == total * 5
        capsys.readouterr()
        assert (
            main.main(["report", "--workspace", str(workspace), "--stage", str(total), "--json"])
            == 0
        )
        report = json.loads(capsys.readouterr().out)
        assert report["completed"] == total
        assert report["arms"][0]["graded"] == total
        assert report["complete"]
    assert main.main(["report", "--workspace", str(workspace), "--stage", "12", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["completed"] == 12
    plan = incremental.Plan(fixture[0])
    plan.verify_stores(fixture[2])  # Fake runs cannot mutate source truth.
    rows = incremental.Ledger(workspace, plan).rows()
    assert len(rows) == 120
    assert len({r["episode_fingerprint"] for r in rows}) == 5


def test_failure_partial_selection_and_interrupt_resume(fixture, tmp_path, capsys):
    workspace = tmp_path / "results"
    plan = incremental.Plan(fixture[0])
    first = plan.stage(12)["added_question_ids"]
    host = fixture[3]
    host.fail = {first[0]}
    assert main.main(command(fixture, workspace, 12, extra=("--question-ids", *first[:5]))) == 1
    assert len(host.calls) == 5
    with pytest.raises(ValueError, match="earlier stage incomplete"):
        main.main(command(fixture, workspace, 24))
    host.fail.clear()
    host.interrupt_at = 8
    with pytest.raises(RuntimeError, match="interrupted"):
        main.main(command(fixture, workspace, 12))
    done = incremental.Ledger(workspace, plan).successful()
    before = len(host.calls)
    host.interrupt_at = None
    assert main.main(command(fixture, workspace, 12)) == 0
    assert len(host.calls) - before == 12 - len(done)
    rows = incremental.Ledger(workspace, plan).rows()
    assert any(r["status"] == "failed" for r in rows)
    assert len(incremental.Ledger(workspace, plan).successful()) == 12


@pytest.mark.parametrize(
    "change", ["config", "judge", "rubric", "feature", "harness", "arm", "version"]
)
def test_changed_conditions_refuse_before_any_calls(fixture, tmp_path, monkeypatch, change):
    workspace = tmp_path / "results"
    assert main.main(command(fixture, workspace, 12)) == 0
    args = command(fixture, workspace, 24)
    if change == "config":
        args += ["--set", "recall.synthesis_hint=false"]
    elif change == "judge":
        fixture[4].spec = dataclasses.replace(fixture[4].spec, model="other-judge")
    elif change == "rubric":
        monkeypatch.setattr(main.judge_module, "RUBRIC", "changed")
    elif change in ("feature", "harness"):
        code = incremental.code_identity()
        code["feature_revision" if change == "feature" else "harness_sha256"] = "changed"
        monkeypatch.setattr(incremental, "code_identity", lambda: code)
    elif change == "arm":
        args[args.index("baseline")] = "progressive"
    else:
        args[args.index("read-v1-replay1")] = "v2"
    before = len(fixture[3].calls), len(fixture[4].calls)
    with pytest.raises(ValueError, match="conditions changed"):
        main.main(args)
    assert before == (len(fixture[3].calls), len(fixture[4].calls))


def test_four_arms_share_manifest_and_explicit_ids_do_not_resample(fixture, tmp_path):
    identities = []
    for arm in ("baseline", "progressive", "overview", "vector"):
        workspace = tmp_path / arm
        assert main.main(command(fixture, workspace, 12, arm)) == 0
        identities.append(json.loads((workspace / "experiment.json").read_text()))
    assert len({x["manifest_sha256"] for x in identities}) == 1
    assert len({x["code"]["harness_sha256"] for x in identities}) == 1
    assert {x["experiment_arm"] for x in identities} == {
        "baseline", "progressive", "overview", "vector"
    }
    episodes = dataset.load(fixture[1])
    ids = [episodes[-1].id, episodes[0].id]
    assert [e.id for e in incremental.select_ids(episodes, ids)] == ids
    with pytest.raises(ValueError):
        incremental.select_ids(episodes, ["missing"])


def test_report_deduplicates_and_rejects_conflicts_and_regrade(fixture, tmp_path, capsys):
    workspace = tmp_path / "results"
    assert main.main(command(fixture, workspace, 12)) == 0
    stage = workspace / "stages/12"
    path = stage / "runs.jsonl"
    original = path.read_text()
    row = json.loads(original.splitlines()[0])
    path.write_text(original + json.dumps(row) + "\n")
    ledger = incremental.Ledger(workspace, incremental.Plan(fixture[0]))
    assert len(ledger.cumulative(12)[0]) == 12
    row["correct"] = not row["correct"]
    path.write_text(original + json.dumps(row) + "\n")
    with pytest.raises(ValueError, match="conflicting"):
        ledger.cumulative(12)
    path.write_text(original)
    with pytest.raises(ValueError, match="immutable"):
        main.main(["regrade", "--workspace", str(stage)])
    meta = json.loads((stage / "run.json").read_text())
    meta["judge_model"] = "changed"
    (stage / "run.json").write_text(json.dumps(meta))
    with pytest.raises(ValueError, match="stage metadata"):
        ledger.cumulative(12)


def test_manifest_and_truth_tampering_fail_before_calls(fixture, tmp_path):
    plan = incremental.Plan(fixture[0])
    q = plan.ids[0]
    name = next(iter(plan.raw["source_store_corpus"]["stores"][q]["files"]))
    (fixture[2] / "W2" / q / name).write_text("changed")
    with pytest.raises(ValueError, match="Store truth changed"):
        main.main(command(fixture, tmp_path / "results", 12))
    assert not fixture[3].calls
    raw = json.loads(fixture[0].read_text())
    raw["stages"][0]["added_question_ids"].reverse()
    fixture[0].write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="checksum"):
        incremental.Plan(fixture[0])


def test_legacy_explicit_selection_keeps_same_set_resume(fixture, tmp_path):
    workspace = tmp_path / "legacy"
    ids = incremental.Plan(fixture[0]).ids[:2]
    args = [
        "run",
        "--suite",
        str(fixture[1]),
        "--workspace",
        str(workspace),
        "--arms",
        "W0",
        "--question-ids",
        *ids,
        "--concurrency",
        "1",
    ]
    assert main.main(args) == 0
    before = len(fixture[3].calls), len(fixture[4].calls)
    assert main.main(args + ["--resume"]) == 0
    assert before == (len(fixture[3].calls), len(fixture[4].calls))
    with pytest.raises(ValueError, match="another experiment"):
        main.main(args + ["--question-ids", *ids, incremental.Plan(fixture[0]).ids[2], "--resume"])


def test_workspace_lock_and_wrong_stage_ids(fixture, tmp_path):
    workspace = tmp_path / "locked"
    with incremental.locked(workspace), pytest.raises(ValueError, match="already in use"):
        main.main(command(fixture, workspace, 12))
    assert not fixture[3].calls
    q = incremental.Plan(fixture[0]).stage(24)["added_question_ids"][0]
    with pytest.raises(ValueError, match="this stage"):
        main.main(command(fixture, tmp_path / "wrong-ids", 12, extra=("--question-ids", q)))
    assert not fixture[3].calls


def test_runtime_rebuilds_index_and_applies_config_without_changing_source(fixture, tmp_path):
    workspace = tmp_path / "results"
    plan = incremental.Plan(fixture[0])
    assert (
        main.main(command(fixture, workspace, 12, extra=("--set", "recall.default_limit=1"))) == 0
    )
    assert "fixture-memory" in fixture[3].observed_hits
    assert set(fixture[3].observed_configs) == {1}
    plan.verify_stores(fixture[2])
    assert not list((workspace / "stages/12").glob("runtime-*"))


def test_runtime_uses_store_configured_indexer(fixture, tmp_path, monkeypatch):
    rebuilt = []

    class ConfiguredStore(Store):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            rebuild = self._indexer.rebuild

            def configured_rebuild():
                rebuilt.append(self.root)
                return rebuild()

            self._indexer.rebuild = configured_rebuild

    monkeypatch.setattr(main, "Store", ConfiguredStore)
    assert main.main(command(fixture, tmp_path / "results", 12)) == 0
    assert len(rebuilt) == 12
    incremental.Plan(fixture[0]).verify_stores(fixture[2])
