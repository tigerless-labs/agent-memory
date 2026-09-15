"""Manifest selection and provenance around the existing driver, sinks and report.

One workspace is one immutable experiment version / logical arm / replay. Stages
retain their own episode fingerprints; only a validated report view is cumulative.
"""

from __future__ import annotations

import contextlib
import dataclasses
import fcntl
import hashlib
import json
import pathlib
import shutil
import subprocess
from collections.abc import Iterator
from typing import Any

from . import dataset, sampling
from .metrics import STATUS_OK, MetricsSink, RunMetadata, RunRecord

STAGES = (12, 24, 48, 96, 120)
IDENTITY_FILE = "experiment.json"
MANIFEST_FILE = "subset.json"


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def file_hash(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_child(root: pathlib.Path, name: str) -> pathlib.Path:
    relative = pathlib.Path(name)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe manifest path: {name}")
    path = root / relative
    if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink():
        raise ValueError(f"unsafe manifest path: {name}")
    return path


class Plan:
    def __init__(self, path: pathlib.Path):
        self.raw = json.loads(path.read_text(encoding="utf-8"))
        unsigned = {k: v for k, v in self.raw.items() if k != "manifest_sha256"}
        if self.raw.get("schema_version") != 1 or digest(unsigned) != self.raw["manifest_sha256"]:
            raise ValueError("invalid manifest checksum/schema")
        self.sha = self.raw["manifest_sha256"]
        self.stages = self.raw["stages"]
        buckets = self.raw["bucket_orders"]
        flattened = [q for order in buckets.values() for q in order]
        if len(flattened) != 120 or len(set(flattened)) != 120:
            raise ValueError("manifest must contain 120 unique question IDs")
        if [s["total"] for s in self.stages] != list(STAGES):
            raise ValueError("manifest stages must be 12/24/48/96/120")
        previous: list[str] = []
        for stage in self.stages:
            added, cumulative = stage["added_question_ids"], stage["cumulative_question_ids"]
            expected = {q for order in buckets.values() for q in order[: stage["per_type"]]}
            if (
                cumulative != previous + added
                or len(set(cumulative)) != stage["total"]
                or len(cumulative) != stage["total"]
                or set(cumulative) != expected
                or stage["added_count"] != len(added)
                or stage["ordered_ids_sha256"] != digest(cumulative)
            ):
                raise ValueError("manifest stages are not nested bucket prefixes")
            previous = cumulative
        self.ids = previous
        stores = self.raw["source_store_corpus"]["stores"]
        if set(stores) != set(self.ids) or set(self.raw["episode_content_sha256"]) != set(self.ids):
            raise ValueError("manifest Store/episode IDs mismatch")

    def stage(self, total: int) -> dict[str, Any]:
        return next(s for s in self.stages if s["total"] == total)

    def episodes(self, suite: pathlib.Path) -> dict[str, dataset.Episode]:
        if file_hash(suite) != self.raw["source_suite"]["sha256"]:
            raise ValueError("suite content changed")
        episodes = dataset.load(suite)
        by_id = {e.id: e for e in episodes}
        if len(by_id) != len(episodes):
            raise ValueError("duplicate suite question IDs")
        for kind, order in self.raw["bucket_orders"].items():
            for q in order:
                if (
                    q not in by_id
                    or by_id[q].question_type != kind
                    or digest(dataclasses.asdict(by_id[q])) != self.raw["episode_content_sha256"][q]
                ):
                    raise ValueError(f"episode content/type changed: {q}")
        for stage in self.stages:
            selected = sorted(
                (by_id[q] for q in stage["cumulative_question_ids"]),
                key=lambda e: (e.question_type, e.id),
            )
            if sampling.fingerprint(selected) != stage["harness_episode_fingerprint"]:
                raise ValueError("manifest episode fingerprint mismatch")
        if self.stages[-1]["harness_episode_fingerprint"] != self.raw["source_episode_fingerprint"]:
            raise ValueError("source episode fingerprint mismatch")
        return {q: by_id[q] for q in self.ids}

    def verify_stores(self, root: pathlib.Path) -> None:
        truth = {}
        arm = self.raw["source_store_corpus"]["arm"]
        for q, store in self.raw["source_store_corpus"]["stores"].items():
            files = {}
            for name, expected in store["files"].items():
                relative = f"{arm}/{q}/{name}"
                actual = file_hash(safe_child(root, relative))
                if actual != expected:
                    raise ValueError(f"Store truth changed: {relative}")
                files[name] = actual
                truth[relative] = actual
            if digest(files) != store["truth_sha256"]:
                raise ValueError("Store fingerprint mismatch")
        if digest(truth) != self.raw["source_store_corpus"]["truth_sha256"]:
            raise ValueError("Store corpus fingerprint mismatch")

    def copy_question(self, root: pathlib.Path, target: pathlib.Path, question: str) -> None:
        """Only manifest-listed truth enters a fresh runtime; never copy source caches."""
        arm = self.raw["source_store_corpus"]["arm"]
        for name, expected in self.raw["source_store_corpus"]["stores"][question]["files"].items():
            relative = f"{arm}/{question}/{name}"
            source, destination = safe_child(root, relative), safe_child(target, relative)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            if file_hash(destination) != expected:
                raise ValueError(f"Store changed while copying: {relative}")


def select_ids(episodes: list[dataset.Episode], identifiers: list[str]) -> list[dataset.Episode]:
    by_id = {e.id: e for e in episodes}
    if len(by_id) != len(episodes) or len(set(identifiers)) != len(identifiers):
        raise ValueError("duplicate question IDs")
    if not identifiers or set(identifiers) - by_id.keys():
        raise ValueError("empty/unknown question IDs")
    return [by_id[q] for q in identifiers]


def code_identity() -> dict[str, Any]:
    """Actual checkout revision plus installed Python source content, including dirty edits."""
    root = pathlib.Path(
        subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
    )
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    sources = {
        p.relative_to(root).as_posix(): file_hash(p)
        for p in sorted((root / "packages").glob("*/src/**/*.py"))
    }
    from agent_memory.core import config
    from agent_memory.executor import hosts

    for module in (config, hosts, dataset):
        if not pathlib.Path(module.__file__ or "").resolve().is_relative_to(root):
            raise ValueError("installed packages must come from this feature checkout")
    shared = {
        p: h
        for p, h in sources.items()
        if p.startswith(("packages/harness/", "packages/executor/"))
        or p.endswith("/core/access_log.py")
    }
    return {
        "feature_revision": revision,
        "source_sha256": digest(sources),
        "harness_sha256": digest(shared),
        "source_files": sources,
    }


def identity(
    metadata: RunMetadata,
    plan: Plan,
    experiment: str,
    arm: str,
    host_spec: Any,
    judge_spec: Any,
    options: dict[str, Any],
) -> dict[str, Any]:
    conditions = metadata.as_dict()
    for execution_field in ("run_id", "episode_fingerprint", "reuse_stores", "code_revision"):
        conditions.pop(execution_field)
    binaries = {}
    for role, spec in (("host", host_spec), ("judge", judge_spec)):
        executable = shutil.which(spec.binary)
        binaries[role] = file_hash(pathlib.Path(executable)) if executable else None
    return {
        "binary_sha256": binaries,
        "schema_version": 1,
        "experiment_version": experiment,
        "experiment_arm": arm,
        "manifest_sha256": plan.sha,
        "store_truth_sha256": plan.raw["source_store_corpus"]["truth_sha256"],
        "conditions": conditions,
        "code": code_identity(),
        "host_spec": dataclasses.asdict(host_spec),
        "judge_spec": dataclasses.asdict(judge_spec),
        "evaluation": options,
    }


@contextlib.contextmanager
def locked(folder: pathlib.Path) -> Iterator[None]:
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / ".incremental.lock").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("incremental workspace is already in use") from error
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def atomic_json(path: pathlib.Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


class StageSink(MetricsSink):
    """Keep all attempts, atomically replacing the JSONL file to avoid torn appends."""

    def __init__(self, folder: pathlib.Path, identity_sha256: str = ""):
        super().__init__(folder)
        self.identity_sha256 = identity_sha256

    def append(self, record: RunRecord) -> None:
        rows = self.records() + [record.as_dict() | {"identity_sha256": self.identity_sha256}]
        temporary = self.path.with_suffix(".jsonl.tmp")
        temporary.write_text(
            "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8"
        )
        temporary.replace(self.path)


class Ledger:
    def __init__(self, folder: pathlib.Path, plan: Plan):
        self.folder, self.plan = folder, plan

    def ensure(self, expected: dict[str, Any]) -> None:
        expected = json.loads(json.dumps(expected))
        path = self.folder / IDENTITY_FILE
        if path.exists():
            if json.loads(path.read_text()) != expected:
                raise ValueError(
                    "experiment conditions changed; use a new experiment version/workspace"
                )
            if Plan(self.folder / MANIFEST_FILE).sha != self.plan.sha:
                raise ValueError("workspace manifest changed")
        else:
            if any(self.folder.rglob("runs.jsonl")) or (self.folder / "run.json").exists():
                raise ValueError("existing records have no incremental identity")
            atomic_json(self.folder / MANIFEST_FILE, self.plan.raw)
            atomic_json(path, expected)

    def rows(self) -> list[dict[str, Any]]:
        identity_data = json.loads((self.folder / IDENTITY_FILE).read_text())
        if identity_data["manifest_sha256"] != self.plan.sha:
            raise ValueError("workspace manifest/identity mismatch")
        result = []
        for stage in self.plan.stages:
            folder = self.folder / "stages" / str(stage["total"])
            if not folder.exists():
                continue
            meta = json.loads((folder / "run.json").read_text())
            expected = identity_data["conditions"] | {
                "run_id": meta["run_id"],
                "code_revision": identity_data["code"]["feature_revision"],
                "reuse_stores": self.plan.raw["source_store_corpus"]["path"],
                "episode_fingerprint": sampling.fingerprint(
                    [_id_episode(q) for q in stage["added_question_ids"]]
                ),
            }
            if meta != expected:
                raise ValueError("stage metadata changed (including regrade); cannot accumulate")
            questions = set(stage["added_question_ids"])
            for row in StageSink(folder).records():
                if (
                    row.get("identity_sha256") != digest(identity_data)
                    or row.get("manage", "") != identity_data["evaluation"]["manage"]
                    or row.get("recall_fingerprint")
                    != identity_data["evaluation"]["recall_fingerprint"]
                    or row["episode_id"] not in questions
                    or row["arm"] != self.plan.raw["source_store_corpus"]["arm"]
                    or any(row.get(k) != meta[k] for k in ("episode_fingerprint", "host", "system"))
                ):
                    raise ValueError("record does not belong to this stage/experiment")
                result.append(row)
        return result

    def successful(self) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for row in self.rows():
            if row["status"] == STATUS_OK:
                q = row["episode_id"]
                if q in result and row != result[q]:
                    raise ValueError(f"conflicting successful records: {q}")
                result[q] = row
        return result

    def pending(self, total: int, only: list[str] | None = None) -> list[str]:
        stage = self.plan.stage(total)
        done = self.successful()
        prior = set(stage["cumulative_question_ids"]) - set(stage["added_question_ids"])
        if prior - done.keys():
            raise ValueError("earlier stage incomplete; resume it before expanding")
        chosen = stage["added_question_ids"]
        if only is not None:
            if not only or len(set(only)) != len(only) or set(only) - set(chosen):
                raise ValueError("question IDs must belong to this stage's added IDs")
            chosen = [q for q in chosen if q in only]
        return [q for q in chosen if q not in done]

    def cumulative(self, total: int) -> tuple[list[dict[str, Any]], list[str]]:
        stage = self.plan.stage(total)
        done = self.successful()
        rows, missing = [], []
        for q in stage["cumulative_question_ids"]:
            if q in done:
                # View only. The persisted stage fingerprints are never rewritten.
                rows.append(done[q] | {"episode_fingerprint": stage["harness_episode_fingerprint"]})
            else:
                missing.append(q)
        return rows, missing


def _id_episode(identifier: str) -> dataset.Episode:
    return dataset.Episode(identifier, "", "", "", "", (), ())
