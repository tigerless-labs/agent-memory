import json

import pytest
from agent_memory.cli.main import main
from agent_memory.core import distill, sessions
from agent_memory.core.errors import NotFoundError, ValidationError


def test_auto_write_keeps_distinct_supporting_ranges(store):
    pointer = store.archive.append_session(
        "migration",
        [
            "user: Project uses uv.",
            "user: Poetry slowed CI, so we migrated to uv.",
            "user: Migration finished September 3.",
        ],
    )
    reply = json.dumps(
        {
            "op": "new",
            "type": "fact",
            "fields": {"subject": "migration"},
            "abstract": "Project uses uv",
            "body": "Poetry slowed CI.",
            "provenance": ["0", "1", "1", "0-0"],
        }
    )
    report = distill.distill(
        store, "migration", sessions.resolve(store.layout, pointer), lambda _: reply
    )
    record = store.find(report.batches[0].written[0])
    assert record is not None
    assert record.provenance == ["sessions/migration#0-0", "sessions/migration#1-1"]


@pytest.mark.parametrize("ranges", [[], ["9"], ["other#0"], ["sessions/elsewhere#0"], ["0-9"]])
def test_auto_write_rejects_missing_or_invalid_ranges(store, ranges):
    pointer = store.archive.append_session("source", ["user: A fact."])
    reply = json.dumps(
        {
            "op": "new",
            "type": "fact",
            "fields": {"subject": "fact"},
            "abstract": "A fact",
            "provenance": ranges,
        }
    )
    report = distill.distill(
        store, "source", sessions.resolve(store.layout, pointer), lambda _: reply
    )
    assert not report.batches[0].written
    assert not store.records()


def test_baseline_mode_preserves_latest_main_batch_fallback_for_paired_experiment(store):
    store.config.write.evidence_linked = False
    pointer = store.archive.append_session("source", ["user: First", "user: Second"])
    reply = json.dumps(
        {
            "op": "new",
            "type": "fact",
            "fields": {"subject": "baseline"},
            "abstract": "First",
            "provenance": [],
        }
    )
    report = distill.distill(
        store, "source", sessions.resolve(store.layout, pointer), lambda _: reply
    )
    record = store.find(report.batches[0].written[0])
    assert record is not None
    assert record.provenance == ["sessions/source#0-1"]


def test_manual_record_without_provenance_remains_valid(store):
    record = store.record(type="fact", fields={"subject": "manual"}, abstract="Manual fact")
    assert record.provenance == []


def test_exact_and_bounded_recovery_stay_in_memory_source(store):
    store.archive.append_session(
        "source", ["user: Project uses uv.", "user: Migration happened because Poetry slowed CI."]
    )
    store.archive.append_session(
        "other", ["user: Migration happened because unrelated reason Poetry slowed CI."]
    )
    record = store.record(
        type="fact",
        fields={"subject": "uv"},
        abstract="Project uses uv",
        provenance=["sessions/source#0"],
    )
    exact = store.trace_evidence(record.name).as_dict()
    assert "Poetry" not in json.dumps(exact)
    results = store.search_source(record.name, "why migration happened Poetry slowed CI")
    assert results and any("Poetry slowed CI" in item["excerpt"] for item in results)
    assert all(item["session"] == "source" for item in results)
    assert all(
        len(item["excerpt"]) <= store.config.recall.source_search_excerpt_chars for item in results
    )


def test_source_search_requires_provenance(store):
    record = store.record(type="fact", fields={"subject": "manual"}, abstract="Manual fact")
    with pytest.raises(ValidationError, match="unavailable"):
        store.search_source(record.name, "manual")


def test_trace_rejects_unbound_range_and_missing_messages(store):
    store.archive.append_session("source", ["user: One", "user: Two"])
    record = store.record(
        type="fact", fields={"subject": "one"}, abstract="One", provenance=["sessions/source#0"]
    )
    assert [
        message.index for message in store.trace_evidence(record.name).evidence[0].messages
    ] == [0]
    with pytest.raises(ValidationError, match="not a range cited"):
        store.trace_evidence(record.name, "sessions/source#1")
    record.provenance = ["sessions/source#0-9"]
    record.path.write_text(record.to_text())
    with pytest.raises(ValidationError, match="missing or inconsistent"):
        store.trace_evidence(record.name)


def test_trace_rejects_traversal_and_symlink_escape(store, tmp_path):
    store.archive.append_session("source", ["user: One"])
    record = store.record(
        type="fact", fields={"subject": "one"}, abstract="One", provenance=["sessions/source#0"]
    )
    with pytest.raises(ValidationError):
        store.trace_evidence(record.name, "sessions/../source#0")
    outside = tmp_path / "outside.jsonl"
    outside.write_text("user: hidden\n")
    path = sessions.session_path(store.layout, "source")
    path.unlink()
    path.symlink_to(outside)
    with pytest.raises(ValidationError, match="redirects"):
        store.trace_evidence(record.name)


def test_search_top_k_and_total_budget(store):
    store.archive.append_session(
        "source",
        [
            "user: Red migration reason alpha.",
            "user: Blue migration reason beta.",
            "user: Green migration reason gamma.",
        ],
    )
    record = store.record(
        type="fact",
        fields={"subject": "colors"},
        abstract="Colors",
        provenance=["sessions/source#0"],
    )
    store.config.index.raw_chunk_chars = 1
    store.config.recall.source_search_total_chars = 25
    hits = store.search_source(record.name, "migration reason", top_k=2)
    assert 0 < len(hits) <= 2
    assert sum(len(hit["excerpt"]) for hit in hits) <= 25


def test_supersede_and_rebuild_preserve_separate_evidence(store):
    store.archive.append_session("old", ["user: We used Poetry."])
    store.archive.append_session("new", ["user: We now use uv."])
    old = store.record(
        type="fact",
        fields={"subject": "package tool"},
        abstract="Uses Poetry",
        provenance=["sessions/old#0"],
    )
    new = store.record(
        type="fact",
        fields={"subject": "package tool"},
        abstract="Uses uv",
        provenance=["sessions/new#0"],
        supersedes=old.name,
    )
    store.rebuild_index()
    assert store.find(old.name).provenance == ["sessions/old#0"]
    assert store.find(new.name).provenance == ["sessions/new#0"]
    store.delete(new.name)
    assert "We now use uv" in store.trace_evidence(new.name).evidence[0].messages[0].text


def test_correct_preserves_evidence(store):
    store.archive.append_session("source", ["user: Project uses uv."])
    record = store.record(
        type="fact", fields={"subject": "uv"}, abstract="Uses uv", provenance=["sessions/source#0"]
    )
    store.correct(record.name, abstract="Project uses uv")
    assert store.find(record.name).provenance == ["sessions/source#0"]


def test_search_fails_when_bound_source_is_missing(store):
    store.archive.append_session("source", ["user: A fact."])
    record = store.record(
        type="fact", fields={"subject": "fact"}, abstract="A fact", provenance=["sessions/source#0"]
    )
    sessions.session_path(store.layout, "source").unlink()
    with pytest.raises(NotFoundError):
        store.search_source(record.name, "fact")


def test_exact_trace_output_budget(store):
    store.archive.append_session("source", ["user: One", "user: Two"])
    record = store.record(
        type="fact", fields={"subject": "one"}, abstract="One", provenance=["sessions/source#0-1"]
    )
    store.config.recall.trace_max_messages = 1
    with pytest.raises(ValidationError, match="output budget"):
        store.trace_evidence(record.name)


def test_cli_trace_exact_then_source_search(store, capsys):
    store.archive.append_session(
        "source",
        [
            "user: Project uses uv.",
            "user: Poetry slowed CI, so the project migrated.",
        ],
    )
    record = store.record(
        type="fact", fields={"subject": "uv"}, abstract="Uses uv", provenance=["sessions/source#0"]
    )
    prefix = ["--store", str(store.root), "--json", "trace", record.name]
    assert main([*prefix, "--pointer", "sessions/source#0"]) == 0
    exact = json.loads(capsys.readouterr().out)
    assert len(exact["messages"]) == 1
    assert main([*prefix, "--query", "Poetry slowed CI", "--top-k", "1"]) == 0
    searched = json.loads(capsys.readouterr().out)
    assert len(searched["hits"]) == 1
    assert "Poetry" in searched["hits"][0]["excerpt"]


def test_legacy_provenance_cannot_traverse_or_follow_symlinks(store, tmp_path):
    record = store.record(
        type="fact",
        fields={"subject": "legacy"},
        abstract="Legacy",
        provenance=["historical excerpt"],
    )
    outside = tmp_path / "outside.md"
    outside.write_text("private")
    record.provenance = ["../../outside.md"]
    record.path.write_text(record.to_text())
    with pytest.raises(ValidationError, match="unsupported provenance"):
        store.trace_evidence(record.name)
    reference = "archive/provenance/legacy/escape.md"
    linked = store.root / reference
    linked.parent.mkdir(parents=True, exist_ok=True)
    linked.symlink_to(outside)
    record.provenance = [reference]
    record.path.write_text(record.to_text())
    with pytest.raises(ValidationError, match="redirects"):
        store.trace_evidence(record.name)
