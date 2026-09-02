"""M3 — the CLI surface, exercised as an operator would."""

import json

import pytest
from agent_memory.cli.main import EXIT_INVALID, EXIT_OK, main
from agent_memory.core.recall import Recall
from agent_memory.core.store import Store


@pytest.fixture
def cli(tmp_path, capsys):
    root = tmp_path / "store"

    def run(*argv, expect=EXIT_OK):
        code = main(["--store", str(root), "--json", *argv])
        captured = capsys.readouterr()
        assert code == expect, captured.err or captured.out
        stream = captured.out if code == EXIT_OK else captured.err
        return json.loads(stream) if stream.strip() else {}

    run("init")
    run.root = root
    return run


def test_init_then_record_then_recall_round_trip(cli):
    cli(
        "record",
        "--abstract",
        "The release pipeline refuses tags that are not signed",
        "--type",
        "procedure",
        "--domain",
        "project",
        "--name",
        "signed-tags-only",
        "--body",
        "# Why\nUnsigned tags cannot be attributed.\n",
    )
    payload = cli("recall", "signed tags release pipeline")
    assert payload["hits"]
    assert payload["hits"][0]["name"] == "signed-tags-only"
    assert set(payload["hits"][0]) >= {"name", "path", "abstract", "anchor", "score"}


def test_invalid_write_returns_a_structured_error_and_a_distinct_exit_code(cli):
    payload = cli(
        "record",
        "--abstract",
        "Wrong domain for this type",
        "--type",
        "reference",
        "--domain",
        "user",
        "--name",
        "wrong-domain",
        expect=EXIT_INVALID,
    )
    assert payload["code"] == "validation_error"
    assert any(error["field"] == "type" for error in payload["errors"])


def test_read_levels_are_available_from_the_command_line(cli):
    cli(
        "record",
        "--abstract",
        "Runbook for draining the queue safely",
        "--type",
        "procedure",
        "--domain",
        "project",
        "--name",
        "queue-drain-runbook",
        "--body",
        "# Prepare\nStop producers.\n\n# Drain\nWait for the lease to expire.\n",
    )
    assert cli("read", "queue-drain-runbook", "--level", "outline")["outline"] == [
        "Prepare",
        "Drain",
    ]
    assert "Stop producers" in cli("read", "queue-drain-runbook")["text"]


def test_correct_supersede_removes_the_old_entry_from_default_recall(cli):
    cli("record", "--abstract", "Timeout is 30s", "--type", "fact", "--domain", "project",
        "--name", "timeout-old")
    cli("record", "--abstract", "Timeout is 60s", "--type", "fact", "--domain", "project",
        "--name", "timeout-new")
    cli("correct", "timeout-old", "--supersede-with", "timeout-new")
    names = [hit["name"] for hit in cli("recall", "timeout")["hits"]]
    assert "timeout-old" not in names
    assert "timeout-new" in names


def test_export_import_round_trip_preserves_the_recall_result_set(cli, tmp_path):
    cli("record", "--abstract", "Alpha memory about queue drains", "--type", "fact",
        "--domain", "project", "--name", "alpha")
    cli("record", "--abstract", "Beta memory about signed release tags", "--type", "fact",
        "--domain", "project", "--name", "beta")
    dump = tmp_path / "dump.json"
    cli("export", "--out", str(dump))

    source = Store(cli.root)
    queries = ["queue drains", "signed release tags"]
    before = {query: {hit.name for hit in Recall(source).recall(query)} for query in queries}

    destination_root = tmp_path / "migrated"
    assert main(["--store", str(destination_root), "--json", "init"]) == EXIT_OK
    assert main(["--store", str(destination_root), "--json", "import", str(dump)]) == EXIT_OK

    destination = Store(destination_root)
    after = {query: {hit.name for hit in Recall(destination).recall(query)} for query in queries}
    assert after == before


def test_inspect_reports_the_recall_fingerprint_that_licenses_attribution(cli):
    payload = cli("inspect")
    assert payload["recall_fingerprint"]
    assert payload["recall_fingerprint"] == cli("inspect")["recall_fingerprint"]


def test_rebuild_from_the_command_line_is_lossless(cli):
    cli("record", "--abstract", "Something worth keeping across a rebuild", "--type", "fact",
        "--domain", "project", "--name", "keeper")
    before = {hit["name"] for hit in cli("recall", "keeping rebuild")["hits"]}
    (cli.root / ".index" / "index.db").unlink()
    cli("rebuild")
    assert {hit["name"] for hit in cli("recall", "keeping rebuild")["hits"]} == before


def test_a_batch_of_memories_is_written_in_one_call(cli, tmp_path):
    batch = tmp_path / "batch.jsonl"
    batch.write_text(
        "\n".join(
            [
                json.dumps({"domain": "user", "type": "fact", "abstract": "Owns a 2019 Subaru"}),
                json.dumps(
                    {"domain": "user", "type": "preference", "abstract": "Prefers oat milk"}
                ),
                json.dumps({"domain": "user", "type": "reference", "abstract": "wrong type here"}),
            ]
        ),
        encoding="utf-8",
    )
    payload = cli("record", "--batch", str(batch))

    assert len(payload["written"]) == 2
    assert len(payload["rejected"]) == 1
    assert payload["rejected"][0]["index"] == 2
    assert payload["rejected"][0]["errors"][0]["field"] == "type"

    names = {hit["name"] for hit in cli("recall", "subaru oat milk")["hits"]}
    assert len(names) == 2


def test_record_without_a_batch_still_demands_its_fields(cli):
    payload = cli("record", "--abstract", "only an abstract", expect=EXIT_INVALID)
    assert payload["code"] == "validation_error"
    assert {error["field"] for error in payload["errors"]} == {"type", "domain"}


def test_a_malformed_batch_line_names_the_line(cli, tmp_path):
    batch = tmp_path / "bad.jsonl"
    batch.write_text('{"domain": "user"\n', encoding="utf-8")
    payload = cli("record", "--batch", str(batch), expect=EXIT_INVALID)
    assert "line 1" in payload["errors"][0]["field"]
