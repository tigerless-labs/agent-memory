import builtins
import dataclasses

import pytest
from agent_memory.core.config import Config
from agent_memory.core.database import Database
from agent_memory.core.embeddings import FastEmbedder
from agent_memory.core.recall import Recall, fuse_candidates
from agent_memory.core.search_index import Candidate
from agent_memory.core.store import Store
from agent_memory.core.vector_index import VectorIndex


class FakeEmbedder:
    def __init__(self):
        self.document_batches: list[list[str]] = []
        self.queries: list[str] = []

    def _vector(self, text: str) -> list[float]:
        lowered = text.lower()
        semantic = ("automobile", "maintenance", "service the car", "vehicle upkeep")
        lifecycle = ("forbidden-semantic", "lifecycle query")
        if any(token in lowered for token in semantic):
            return [1.0, 0.0, 0.0]
        if any(token in lowered for token in lifecycle):
            return [0.0, 1.0, 0.0]
        return [0.0, 0.0, 1.0]

    def embed_documents(self, texts):
        self.document_batches.append(list(texts))
        return [self._vector(text) for text in texts]

    def embed_query(self, text):
        self.queries.append(text)
        return self._vector(text)


def _vector_store(root, clock, model="fake/v1"):
    config = Config.default()
    config.index.vector_enabled = True
    config.index.vector_model = model
    embedder = FakeEmbedder()
    return Store(root, config=config, clock=clock, embedder=embedder), embedder


def _candidate(name, relevance=1.0, kind="body", anchor="", heading=""):
    return Candidate(name, kind, anchor, heading, relevance)


def test_rrf_keeps_both_sources_boosts_overlap_deduplicates_and_is_deterministic():
    lexical = [_candidate("both"), _candidate("lexical"), _candidate("both")]
    dense = [_candidate("both"), _candidate("dense")]
    first = fuse_candidates(lexical, dense, 10)
    second = fuse_candidates(lexical, dense, 10)
    assert first == second
    assert [item.name for item in first] == ["both", "dense", "lexical"]
    assert first[0].relevance > first[1].relevance
    assert len(fuse_candidates(lexical, dense, 2)) == 2


def test_vector_only_semantic_candidate_enters_recall(tmp_path, clock):
    plain = Store(tmp_path / "plain", clock=clock)
    plain.init()
    plain.record(abstract="Automobile maintenance schedule", type="fact", domain="project",
                 name="vehicle-upkeep")
    assert "vehicle-upkeep" not in [hit.name for hit in Recall(plain).recall("service the car")]

    vector, _ = _vector_store(tmp_path / "vector", clock)
    vector.init()
    vector.record(abstract="Automobile maintenance schedule", type="fact", domain="project",
                  name="vehicle-upkeep")
    assert "vehicle-upkeep" in [hit.name for hit in Recall(vector).recall("service the car")]


def test_disabled_store_never_constructs_or_calls_an_embedder(monkeypatch, tmp_path, clock):
    def forbidden(_model):
        raise AssertionError("embedding backend was instantiated")

    monkeypatch.setattr("agent_memory.core.store.create_embedder", forbidden)
    store = Store(tmp_path / "store", clock=clock)
    store.init()
    store.record(abstract="plain lexical memory", type="fact", domain="project")
    Recall(store).recall("plain lexical")


def test_enabled_store_explains_how_to_install_a_missing_backend(monkeypatch):
    real_import = builtins.__import__

    def missing(name, *args, **kwargs):
        if name == "fastembed":
            raise ImportError("not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing)
    with pytest.raises(RuntimeError, match=r"enabled.*unavailable.*agent-memory-core\[vector\]"):
        FastEmbedder("fake/model")


def test_off_to_on_bootstraps_without_filesystem_changes(tmp_path, clock):
    root = tmp_path / "store"
    plain = Store(root, clock=clock)
    plain.init()
    plain.record(abstract="Automobile maintenance schedule", type="fact", domain="project",
                 name="vehicle-upkeep")
    vector, embedder = _vector_store(root, clock)
    report = vector.sync_index()
    assert report.reindexed == ()
    assert embedder.document_batches
    assert "vehicle-upkeep" in [hit.name for hit in Recall(vector).recall("service the car")]


def test_incremental_updates_offline_catchup_delete_and_model_change(tmp_path, clock):
    root = tmp_path / "store"
    store, embedder = _vector_store(root, clock)
    store.init()
    store.record(abstract="Automobile maintenance schedule", type="fact", domain="project",
                 name="vehicle-upkeep")
    store.record(abstract="Unrelated stable note", type="fact", domain="project",
                 name="stable-note")
    embedder.document_batches.clear()
    target = store.find("vehicle-upkeep")
    target.body = "Vehicle upkeep details"
    target.path.write_text(target.to_text(), encoding="utf-8")
    store.sync_index()
    assert len(embedder.document_batches) == 1

    off_config = dataclasses.replace(store.config)
    off_config.index = dataclasses.replace(store.config.index, vector_enabled=False)
    offline = Store(root, config=off_config, clock=clock)
    stable = offline.find("stable-note")
    stable.body = "changed while vectors are disabled"
    stable.path.write_text(stable.to_text(), encoding="utf-8")
    offline.sync_index()
    assert len(embedder.document_batches) == 1
    store.sync_index()
    assert len(embedder.document_batches) == 2

    store.find("stable-note").path.unlink()
    store.sync_index()
    with Database(store.layout).connect() as connection:
        assert "stable-note" not in {
            row["name"] for row in connection.execute("SELECT name FROM vector_chunks")
        }

    changed, changed_embedder = _vector_store(root, clock, model="fake/v2")
    changed.sync_index()
    assert len(changed_embedder.document_batches) == 1
    with Database(changed.layout).connect() as connection:
        assert {row["model"] for row in connection.execute("SELECT model FROM vector_files")} == {
            "fake/v2"
        }


def test_vector_rebuild_preserves_recall_set(tmp_path, clock):
    store, _ = _vector_store(tmp_path / "store", clock)
    store.init()
    store.record(abstract="Automobile maintenance schedule", type="fact", domain="project",
                 name="vehicle-upkeep")
    before = {hit.name for hit in Recall(store).recall("service the car")}
    store.layout.index_db.unlink()
    store.rebuild_index()
    assert {hit.name for hit in Recall(store).recall("service the car")} == before


def test_vector_candidates_cannot_bypass_lifecycle_or_scope(tmp_path, clock):
    store, _ = _vector_store(tmp_path / "store", clock)
    store.init()
    store.record(abstract="forbidden-semantic old", type="fact", domain="project",
                 name="old", valid_from="2026-01-01")
    store.record(abstract="forbidden-semantic current", type="fact", domain="project",
                 name="current", valid_from="2026-01-10")
    store.correct("old", supersede_with="current")
    store.record(abstract="forbidden-semantic retired", type="fact", domain="user",
                 name="retired")
    store.retire("retired")
    names = [hit.name for hit in Recall(store).recall("lifecycle query", scope="project")]
    assert "current" in names
    assert "old" not in names
    assert "retired" not in names
    historical = [
        hit.name for hit in Recall(store).recall("lifecycle query", as_of="2026-01-05")
    ]
    assert "old" in historical
    assert "current" not in historical


def test_vector_candidates_still_use_recency_and_weight(tmp_path, clock):
    store, _ = _vector_store(tmp_path / "store", clock)
    store.init()
    store.record(abstract="forbidden-semantic older", type="fact", domain="project",
                 name="a-older")
    store.record(abstract="forbidden-semantic newer", type="fact", domain="project",
                 name="z-newer")
    older = store.find("a-older")
    older.updated = "2020-01-01T00:00:00Z"
    older.path.write_text(older.to_text(), encoding="utf-8")
    store.sync_index()

    recency_ranked = [hit.name for hit in Recall(store).recall("lifecycle query")]
    assert recency_ranked.index("z-newer") < recency_ranked.index("a-older")
    store.feedback("a-older", store.config.weight.ceiling)
    weight_ranked = [hit.name for hit in Recall(store).recall("lifecycle query")]
    assert weight_ranked.index("a-older") < weight_ranked.index("z-newer")


def test_vector_match_restores_chunk_metadata(tmp_path, clock):
    store, embedder = _vector_store(tmp_path / "store", clock)
    store.init()
    store.record(abstract="Automobile maintenance schedule", type="fact", domain="project",
                 name="vehicle-upkeep", body="# Service\nVehicle upkeep")
    with Database(store.layout).connect() as connection:
        candidates = VectorIndex(connection, embedder, "fake/v1").match("service the car", 10)
    assert {(item.name, item.kind, item.anchor, item.heading) for item in candidates}


def test_hybrid_deep_raw_scores_stay_below_relevant_memory(tmp_path, clock):
    store, _ = _vector_store(tmp_path / "store", clock)
    store.init()
    store.record(abstract="Aquarium ticket evidence costs 42 dollars", type="fact",
                 domain="project", name="ticket-memory")
    store.archive.append_session(
        "ticket-session", "aquarium ticket evidence costs 42 dollars " * 20
    )
    store.sync_index()
    hits = Recall(store).recall("aquarium ticket evidence 42 dollars", deep=True)
    memory = next(hit for hit in hits if hit.name == "ticket-memory")
    raw = [hit for hit in hits if hit.source == "raw"]
    assert raw
    assert max(hit.score for hit in raw) < memory.score
