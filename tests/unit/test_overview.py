"""Virtual L1 mechanics, entirely deterministic and offline."""

import dataclasses

import pytest
from agent_memory.core import context, overview
from agent_memory.core.access_log import AccessLog
from agent_memory.core.database import Database
from agent_memory.core.errors import NotFoundError, ValidationError
from agent_memory.core.recall import Recall


def write(store, name, **kwargs):
    return store.record(
        name=name, abstract=kwargs.pop("abstract", f"Navigation fixture {name}"),
        domain="project", type="fact", topic=kwargs.pop("topic", "deploy"),
        body=f"PRIVATE BODY {name}", **kwargs,
    )


def names(view):
    return [entry.name for entry in view.entries]


@pytest.fixture
def deployment(store):
    write(store, "switch-to-uv", abstract="Package manager migration to uv")
    write(store, "ci-change", abstract="CI configuration adjustments")
    write(store, "rollback", abstract="Rollback procedure")
    return store


def test_navigation_finds_an_unmatched_sibling_then_reads_only_selected_body(deployment):
    hits = Recall(deployment).recall("migration")
    assert [hit.name for hit in hits] == ["switch-to-uv"]
    baseline = context.build(deployment, "migration")
    assert baseline.names == ("switch-to-uv",)
    view = overview.build(deployment, hits[0].name)
    assert view.topic == "project/deploy"
    assert names(view) == ["switch-to-uv", "ci-change", "rollback"]
    assert view.entries[1].abstract == "CI configuration adjustments"
    assert "PRIVATE BODY" not in str(view.as_dict())
    assert "PRIVATE BODY ci-change" in deployment.read("ci-change").text
    assert context.build(deployment, "migration") == baseline
    assert [hit.name for hit in Recall(deployment).recall("migration")] == ["switch-to-uv"]


def test_overview_does_not_read_log_write_truth_or_call_retrieval(deployment, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("overview must not open bodies, retrieve, or invoke a reasoner")

    before = {p: p.read_bytes() for p in deployment.root.rglob("*") if p.is_file()}
    with Database(deployment.layout).connect() as connection:
        access_before = AccessLog(connection).entries()
    monkeypatch.setattr(deployment, "read", forbidden)
    monkeypatch.setattr(Recall, "recall", forbidden)
    overview.build(deployment, "switch-to-uv")
    assert {p: p.read_bytes() for p in deployment.root.rglob("*") if p.is_file()} == before
    with Database(deployment.layout).connect() as connection:
        assert AccessLog(connection).entries() == access_before


def test_limits_include_seed_and_order_is_stable(store):
    for number in reversed(range(24)):
        write(store, f"item-{number:02}")
    first = overview.build(store, "item-23")
    assert len(first.entries) == store.config.recall.default_limit
    assert first.truncated
    assert names(first) == ["item-23"] + [f"item-{n:02}" for n in range(7)]
    assert overview.build(store, "item-23") == first
    assert names(overview.build(store, "item-23", limit=1)) == ["item-23"]
    assert not overview.build(store, "item-23", limit=24).truncated


@pytest.mark.parametrize("limit", [0, -1])
def test_invalid_limits(store, limit):
    with pytest.raises(ValidationError, match="must be positive"):
        overview.build(store, "missing", limit=limit)


def test_domain_root_is_not_a_topic_and_other_directories_are_not_expanded(store):
    write(store, "root-seed", topic=None, links=["linked"])
    write(store, "unrelated", topic=None)
    write(store, "linked", topic="elsewhere")
    write(store, "linked-sibling", topic="elsewhere")
    write(store, "nested-seed")
    root = overview.build(store, "root-seed")
    assert root.topic is None
    assert names(root) == ["root-seed", "linked"]
    assert names(overview.build(store, "nested-seed")) == ["nested-seed"]


def test_links_are_outgoing_one_hop_deduplicated_and_missing_targets_ignored(store):
    seed = write(store, "seed", links=["linked", "linked", "missing", "sibling", "seed"])
    write(store, "sibling")
    write(store, "linked", topic="other", links=["seed", "second-hop"])
    write(store, "second-hop", topic="other")
    write(store, "incoming", topic="other", links=["seed"])
    # An externally edited malformed link must not be interpreted as a path.
    seed.links.append("../../outside")
    seed.path.write_text(seed.to_text())
    result = overview.build(store, "seed")
    assert names(result) == ["seed", "sibling", "linked"]
    assert [entry.relation for entry in result.entries] == ["seed", "same-topic", "link"]


@pytest.mark.parametrize("as_of", [None, "2026-01-20", "2026-02-01"])
@pytest.mark.parametrize("scope", [None, "project/deploy", "project/depl"])
def test_lifecycle_scope_and_as_of_match_recall(store, as_of, scope):
    write(store, "seed", valid_from="2026-01-01", links=["outside", "retired"])
    write(store, "poetry", valid_from="2026-01-01")
    write(store, "uv", valid_from="2026-02-01", supersedes="poetry")
    write(store, "retired", valid_from="2026-01-01")
    store.retire("retired")
    stale = write(store, "stale", valid_from="2026-01-01")
    store.write(dataclasses.replace(stale, status="stale"))
    write(store, "outside", topic="other", valid_from="2026-01-01")
    expected = {hit.name for hit in Recall(store).recall(
        "Navigation fixture", scope=scope, as_of=as_of, limit=30,
    )}
    view = overview.build(store, "seed", scope=scope, as_of=as_of, limit=30)
    assert set(names(view)) == expected
    assert "retired" not in names(view)
    assert "stale" in names(view)
    assert view.as_of == as_of


def test_out_of_scope_successor_still_controls_historical_eligibility(store):
    write(store, "seed", valid_from="2026-01-01")
    write(store, "old", valid_from="2026-01-01")
    write(store, "new", topic="other", valid_from="2026-02-01", supersedes="old")
    assert "old" in names(overview.build(
        store, "seed", scope="project/deploy", as_of="2026-01-20",
    ))
    assert names(overview.build(
        store, "seed", scope="project/deploy", as_of="2026-02-01",
    )) == ["seed"]


def test_ineligible_seed_is_not_presented_as_current(store):
    write(store, "old", valid_from="2026-01-01")
    write(store, "new", valid_from="2026-02-01", supersedes="old")
    with pytest.raises(ValidationError, match="not eligible"):
        overview.build(store, "old")
    assert names(overview.build(store, "old", as_of="2026-01-20")) == ["old"]
    with pytest.raises(ValidationError, match="not eligible"):
        overview.build(store, "new", scope="user")
    with pytest.raises(ValidationError, match="not eligible"):
        overview.build(store, "new", as_of="2026-01-20")
    store.retire("new")
    with pytest.raises(ValidationError, match="not eligible"):
        overview.build(store, "new")


def test_missing_seed_and_bad_date_are_explicit_errors(store):
    with pytest.raises(NotFoundError):
        overview.build(store, "missing")
    with pytest.raises(ValidationError, match="ISO 8601"):
        overview.build(store, "missing", as_of="yesterday")


def test_external_edits_moves_and_deletion_are_visible_without_sync(deployment):
    ci = deployment.find("ci-change")
    ci.abstract = "Updated directly on disk"
    ci.path.write_text(ci.to_text())
    assert overview.build(deployment, "switch-to-uv").entries[1].abstract == ci.abstract
    ci.path.rename(deployment.root / "project" / "ci-change.md")
    assert names(overview.build(deployment, "switch-to-uv")) == ["switch-to-uv", "rollback"]
    deployment.find("rollback").path.unlink()
    assert names(overview.build(deployment, "switch-to-uv")) == ["switch-to-uv"]
