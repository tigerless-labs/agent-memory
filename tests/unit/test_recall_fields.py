import json

import pytest
from agent_memory.cli.main import main
from agent_memory.core import context
from agent_memory.core.config import Config
from agent_memory.core.database import Database
from agent_memory.core.errors import ValidationError
from agent_memory.core.recall import Recall
from agent_memory.core.store import Store
from agent_memory.mcp.tools import TOOL_RECALL, dispatch


def names(hits):
    return {hit.name for hit in hits}


def project_memories(store):
    for name, kind, project in [
        ("pagination-design", "decision", "scrapling"),
        ("pagination-cycle", "experience", "scrapling"),
        ("pagination-other", "decision", "other"),
    ]:
        store.record(
            name=name,
            type=kind,
            fields={"project": project},
            abstract="JSON feed pagination",
            body="Follow next_url without cycles.",
        )


def test_fields_retrieve_one_project_across_types_and_compose_with_scope(store):
    project_memories(store)
    recall = Recall(store)
    expected = {"pagination-design", "pagination-cycle"}
    assert names(recall.recall("pagination", fields={"project": "scrapling"})) == expected
    assert names(
        recall.recall("pagination", fields={"project": "scrapling"}, scope="decision")
    ) == {"pagination-design"}
    assert (
        set(context.build(store, "pagination", fields={"project": "scrapling"}).names) == expected
    )
    assert recall.recall("pagination", fields={}) == recall.recall("pagination")


def test_fields_filter_before_lexical_candidate_limit(store):
    count = store.config.recall.candidate_pool_multiplier + 1
    specs = [
        {
            "name": f"outside-{i}",
            "type": "decision",
            "fields": {"project": "other"},
            "abstract": "pagination pagination pagination",
        }
        for i in range(count)
    ]
    specs.append(
        {
            "name": "wanted",
            "type": "experience",
            "fields": {"project": "scrapling"},
            "abstract": "pagination",
        }
    )
    assert not store.record_many(specs).rejected
    assert names(Recall(store).recall("pagination", limit=1, fields={"project": "scrapling"})) == {
        "wanted"
    }


def test_fields_are_literal_conjunctive_and_missing_fields_do_not_match(store):
    store.record(
        name="literal",
        type="decision",
        abstract="pagination",
        fields={"project": "scrapling", "subject": 'JSON%_" OR 1=1 --'},
    )
    recall = Recall(store)
    assert names(
        recall.recall("pagination", fields={"project": "scrapling", "subject": 'JSON%_" OR 1=1 --'})
    ) == {"literal"}
    for fields in [
        {"project": "Scrapling"},
        {"project": "scrapling", "subject": "other"},
        {"unknown": "scrapling"},
        {"subject": "JSON%"},
    ]:
        assert not recall.recall("pagination", fields=fields)


def test_fields_apply_to_history_and_survive_rebuild(store, clock):
    project_memories(store)
    before = clock.now().isoformat()
    truth = {path: path.read_bytes() for path in store.layout.truth_files()}
    Recall(store).recall("pagination", fields={"project": "scrapling"})
    assert all(path.read_bytes() == data for path, data in truth.items())
    clock.advance(days=1)
    store.delete("pagination-cycle")
    store.rebuild_index()
    recall = Recall(store)
    assert names(recall.recall("pagination", fields={"project": "scrapling"})) == {
        "pagination-design"
    }
    assert names(recall.recall("pagination", fields={"project": "scrapling"}, as_of=before)) == {
        "pagination-design",
        "pagination-cycle",
    }


def test_first_filtered_recall_backfills_an_old_index_without_changing_truth(store):
    project_memories(store)
    truth = {path: path.read_bytes() for path in store.layout.truth_files()}
    with Database(store.layout).connect() as connection:
        connection.execute("DROP TABLE record_fields")
        connection.execute("DELETE FROM index_meta WHERE key = 'fields_projection'")
    assert names(Recall(store).recall("pagination", fields={"project": "scrapling"})) == {
        "pagination-design",
        "pagination-cycle",
    }
    assert all(path.read_bytes() == data for path, data in truth.items())


class SameEmbedder:
    def embed_documents(self, texts):
        return [[1.0, 0.0] for _ in texts]

    def embed_query(self, text):
        return [1.0, 0.0]


def test_fields_restrict_vector_candidates_before_the_limit(tmp_path, clock):
    config = Config.default()
    config.index.vector_enabled = True
    config.index.vector_model = "fixture"
    store = Store(tmp_path / "vector", config=config, clock=clock, embedder=SameEmbedder())
    store.init()
    count = config.recall.candidate_pool_multiplier + 1
    for i in range(count):
        store.record(
            name=f"a-other-{i}",
            type="decision",
            abstract="Vehicle maintenance",
            fields={"project": "other"},
        )
    store.record(
        name="z-wanted",
        type="experience",
        abstract="Vehicle maintenance",
        fields={"project": "scrapling"},
    )
    assert names(
        Recall(store).recall("unrelated lexical tokens", limit=1, fields={"project": "scrapling"})
    ) == {"z-wanted"}


def test_cli_and_mcp_share_field_eligibility(store, capsys):
    project_memories(store)
    assert (
        main(
            [
                "--store",
                str(store.root),
                "--json",
                "recall",
                "pagination",
                "--field",
                "project=scrapling",
            ]
        )
        == 0
    )
    cli = json.loads(capsys.readouterr().out)
    mcp = dispatch(store, TOOL_RECALL, {"query": "pagination", "fields": {"project": "scrapling"}})
    assert [(hit["name"], hit["path"]) for hit in cli["hits"]] == [
        (hit["name"], hit["path"]) for hit in mcp["hits"]
    ]
    assert {hit["name"] for hit in cli["hits"]} == {"pagination-design", "pagination-cycle"}
    assert (
        main(
            [
                "--store",
                str(store.root),
                "--json",
                "context",
                "pagination",
                "--field",
                "project=scrapling",
            ]
        )
        == 0
    )
    assert set(json.loads(capsys.readouterr().out)["names"]) == {
        "pagination-design",
        "pagination-cycle",
    }


@pytest.mark.parametrize("fields", [{"project": 42}, ["scrapling"], {"": "scrapling"}])
def test_invalid_field_filters_fail_closed(store, fields):
    with pytest.raises(ValidationError):
        Recall(store).recall("pagination", fields=fields)
    with pytest.raises(ValidationError):
        dispatch(store, TOOL_RECALL, {"query": "pagination", "fields": fields})
