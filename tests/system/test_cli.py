"""M3 — the CLI surface, exercised as an operator would."""

import json

import pytest
from agent_memory.cli.main import EXIT_ERROR, EXIT_INVALID, EXIT_OK, main
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
        "A type nobody declared",
        "--type",
        "nonsense",
        "--name",
        "unknown-type",
        expect=EXIT_INVALID,
    )
    assert payload["code"] == "validation_error"
    assert any(error["field"] == "type" for error in payload["errors"])


def test_a_rejected_write_prints_the_field_and_the_reason(cli, capsys):
    argv = ("record", "--type", "fact", "--abstract", "重构后的部署流程记录")
    (error,) = cli(*argv, expect=EXIT_INVALID)["errors"]
    assert main(["--store", str(cli.root), *argv]) == EXIT_INVALID
    assert f"{error['field']}: {error['reason']}" in capsys.readouterr().err


def test_read_levels_are_available_from_the_command_line(cli):
    cli(
        "record",
        "--abstract",
        "Runbook for draining the queue safely",
        "--type",
        "procedure",
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
    cli("record", "--abstract", "Timeout is 30s", "--type", "fact", "--name", "timeout-old")
    cli("record", "--abstract", "Timeout is 60s", "--type", "fact", "--name", "timeout-new")
    cli("correct", "timeout-old", "--supersede-with", "timeout-new")
    names = [hit["name"] for hit in cli("recall", "timeout")["hits"]]
    assert "timeout-old" not in names
    assert "timeout-new" in names


def test_export_import_round_trip_preserves_the_recall_result_set(cli, tmp_path):
    cli(
        "record",
        "--abstract",
        "Alpha memory about queue drains",
        "--type",
        "fact",
        "--name",
        "alpha",
    )
    cli(
        "record",
        "--abstract",
        "Beta memory about signed release tags",
        "--type",
        "fact",
        "--name",
        "beta",
    )
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
    cli(
        "record",
        "--abstract",
        "Something worth keeping across a rebuild",
        "--type",
        "fact",
        "--name",
        "keeper",
    )
    before = {hit["name"] for hit in cli("recall", "keeping rebuild")["hits"]}
    (cli.root / ".index" / "index.db").unlink()
    cli("rebuild")
    assert {hit["name"] for hit in cli("recall", "keeping rebuild")["hits"]} == before


def test_a_batch_of_memories_is_written_in_one_call(cli, tmp_path):
    batch = tmp_path / "batch.jsonl"
    batch.write_text(
        "\n".join(
            [
                json.dumps({"type": "fact", "abstract": "Owns a 2019 Subaru"}),
                json.dumps({"type": "preference", "abstract": "Prefers oat milk"}),
                json.dumps({"type": "nonsense", "abstract": "wrong type here"}),
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


@pytest.mark.parametrize(
    ("invalid", "field"),
    [
        (
            {"type": "fact", "abstract": "Batch recovery invalid weight", "weight": "oops"},
            "weight",
        ),
        (
            {
                "type": "event",
                "abstract": "Batch recovery invalid date",
                "valid_from": "not-a-date",
            },
            "valid_from",
        ),
        (None, "spec"),
        ([], "spec"),
        ("not an object", "spec"),
        (42, "spec"),
    ],
    ids=["weight", "event-date", "null", "array", "string", "number"],
)
def test_batch_input_rejections_keep_valid_siblings_projected(cli, tmp_path, invalid, field):
    names = ["batch-first", "batch-last"]
    valid = [
        {"type": "fact", "name": name, "abstract": f"Batch recovery accepted {name}"}
        for name in names
    ]
    batch = tmp_path / "mixed-batch.jsonl"
    batch.write_text(
        "\n".join(json.dumps(spec) for spec in [valid[0], invalid, valid[1]]),
        encoding="utf-8",
    )

    payload = cli("record", "--batch", str(batch))

    assert [record["name"] for record in payload["written"]] == names
    assert [item["index"] for item in payload["rejected"]] == [1]
    assert {error["field"] for error in payload["rejected"][0]["errors"]} == {field}
    if field == "spec":
        assert "object" in payload["rejected"][0]["errors"][0]["reason"]
    store = Store(cli.root)
    assert {record.name for record in store.records()} == set(names)
    assert {hit["name"] for hit in cli("recall", "batch recovery")["hits"]} == set(names)
    projected = store.layout.memory_index.read_bytes()
    assert all(name.encode() in projected for name in names)
    assert b"invalid" not in projected

    cli("rebuild")

    assert {hit["name"] for hit in cli("recall", "batch recovery")["hits"]} == set(names)
    assert store.layout.memory_index.read_bytes() == projected


def test_batch_missing_predecessor_rolls_back_accepted_siblings(cli, tmp_path):
    cli(
        "record",
        "--type",
        "fact",
        "--name",
        "batch-original",
        "--abstract",
        "Batch recovery original description",
    )
    store = Store(cli.root)
    original = {path: path.read_bytes() for path in store.layout.truth_files()}
    projected = store.layout.memory_index.read_bytes()
    names = {hit["name"] for hit in cli("recall", "batch recovery")["hits"]}
    batch = tmp_path / "aborted-batch.jsonl"
    specs = [
        {
            "type": "fact",
            "name": "batch-original",
            "abstract": "Batch recovery modified description",
        },
        {"type": "fact", "name": "batch-created", "abstract": "Batch recovery newly created"},
        {
            "type": "fact",
            "name": "batch-successor",
            "abstract": "Batch recovery missing predecessor",
            "supersedes": "batch-missing",
        },
    ]
    batch.write_text("\n".join(json.dumps(spec) for spec in specs), encoding="utf-8")

    payload = cli("record", "--batch", str(batch), expect=EXIT_ERROR)

    assert payload["code"] == "not_found"
    assert "batch-missing" in payload["message"]
    assert {path: path.read_bytes() for path in store.layout.truth_files()} == original
    assert store.layout.memory_index.read_bytes() == projected
    assert {hit["name"] for hit in cli("recall", "batch recovery")["hits"]} == names

    cli("rebuild")

    assert {hit["name"] for hit in cli("recall", "batch recovery")["hits"]} == names
    assert store.layout.memory_index.read_bytes() == projected


def test_record_without_a_batch_still_demands_its_fields(cli):
    payload = cli("record", "--abstract", "only an abstract", expect=EXIT_INVALID)
    assert payload["code"] == "validation_error"
    assert {error["field"] for error in payload["errors"]} == {"type"}


def test_a_malformed_batch_line_names_the_line(cli, tmp_path):
    batch = tmp_path / "bad.jsonl"
    batch.write_text('{"domain": "user"\n', encoding="utf-8")
    payload = cli("record", "--batch", str(batch), expect=EXIT_INVALID)
    assert "line 1" in payload["errors"][0]["field"]


def _near_duplicates(cli):
    for name, extra, body in (
        ("drain-window-first", "", "Short."),
        ("drain-window-second", " again", "Longer body carrying the lease TTL and the fix."),
    ):
        cli(
            "record",
            "--abstract",
            "The drain window closes before the worker lease expires" + extra,
            "--type",
            "experience",
            "--name",
            name,
            "--body",
            body,
        )


def test_proposals_are_listed_with_a_stable_identity(cli):
    _near_duplicates(cli)
    first = cli("proposals")["proposals"]
    second = cli("proposals")["proposals"]
    assert first
    assert [proposal["id"] for proposal in first] == [proposal["id"] for proposal in second]


def test_accepting_a_proposal_applies_it_and_closes_it(cli):
    _near_duplicates(cli)
    proposal = cli("proposals")["proposals"][0]
    decision = cli("decide", proposal["id"], "--accept")
    assert decision["verdict"] == "accepted"
    assert proposal["id"] not in {open_one["id"] for open_one in cli("proposals")["proposals"]}
    kept = cli("read", "drain-window-second")
    assert kept["name"] == "drain-window-second"


def test_deciding_an_unknown_proposal_reports_an_error(cli):
    cli("decide", "0123456789ab", "--accept", expect=EXIT_ERROR)


def test_a_verdict_is_required(cli):
    _near_duplicates(cli)
    proposal = cli("proposals")["proposals"][0]
    with pytest.raises(SystemExit):
        main(["--store", str(cli.root), "--json", "decide", proposal["id"]])


def test_a_sleep_with_nobody_reasoning_decides_nothing(cli):
    _near_duplicates(cli)
    assert not cli("sleep", "--reason", "none")["decisions"]


def _system_group_records(cli):
    return {
        record.name: (
            record.path.relative_to(cli.root),
            record.fields,
            record.valid_from,
            record.body,
            record.provenance,
            record.is_active(),
        )
        for record in Store(cli.root).records(include_invalid=True)
    }


@pytest.mark.parametrize(
    ("memory_type", "group_field", "group"),
    [("fact", "project", "payments"), ("event", "date", "2020-09")],
)
def test_rule_only_sleep_preserves_crowded_system_groups(cli, memory_type, group_field, group):
    names = set()
    for index in range(Store(cli.root).config.manage.cluster_min_files):
        name = f"latency-{index}"
        names.add(name)
        cli(
            "record",
            "--type", memory_type,
            "--name", name,
            "--field", f"{group_field}={group}",
            "--field", f"subject={name}",
            "--abstract", f"Cache latency budget for shard {index}",
            "--body", f"Shard {index} reserves its own cache latency budget.",
            "--valid-from", "2020-09-15",
            "--provenance", f"The operator measured cache latency for shard {index}.",
        )
    scope = f"{memory_type}/{group}"
    before = _system_group_records(cli)
    assert set(before) == names
    assert {hit["name"] for hit in cli("recall", "latency", "--scope", scope)["hits"]} == names

    for command in (("sleep", "--reason", "none"), ("rebuild",), ("sleep", "--reason", "none")):
        cli(*command)
        assert _system_group_records(cli) == before
        assert {
            hit["name"] for hit in cli("recall", "latency", "--scope", scope)["hits"]
        } == names


def test_rule_only_sleep_keeps_similarly_spelled_projects_separate(cli):
    expected = {"payment": "individual-payment", "payments": "aggregate-payments"}
    for project, name in expected.items():
        cli(
            "record",
            "--type", "fact",
            "--name", name,
            "--field", f"project={project}",
            "--field", f"subject={name}",
            "--abstract", f"Retention policy for {name}",
            "--body", f"The {project} service owns this retention policy.",
        )
    before = _system_group_records(cli)

    for command in (("sleep", "--reason", "none"), ("rebuild",), ("sleep", "--reason", "none")):
        cli(*command)
        assert _system_group_records(cli) == before
        for project, name in expected.items():
            assert {
                hit["name"]
                for hit in cli("recall", "retention", "--scope", f"fact/{project}")["hits"]
            } == {name}


@pytest.mark.parametrize(
    "contents",
    [
        (
            ("缓存保存商品价格", "缓存按分钟失效。 Retention."),
            ("订单必须校验库存", "订单提交前检查库存。 Retention."),
        ),
        (
            ("Alice approves Bob", "Retention."),
            ("Bob approves Alice", "Retention."),
        ),
    ],
    ids=["chinese", "word-order"],
)
def test_rule_only_sleep_preserves_distinct_memories_and_projections(cli, contents):
    names = {"distinct-a", "distinct-b"}
    for name, (abstract, body) in zip(sorted(names), contents, strict=True):
        cli(
            "record", "--type", "fact", "--name", name,
            "--abstract", abstract, "--body", body,
            "--field", "project=dedup", "--field", "subject=retention",
            "--valid-from", "2000-01-01",
        )

    report = cli("sleep", "--reason", "none")

    assert not report["decisions"]
    assert not any(action["kind"] == "duplicate-merged" for action in report["actions"])
    assert {record.name for record in Store(cli.root).records()} == names
    assert {hit["name"] for hit in cli("recall", "retention")["hits"]} == names
    memory_index = (cli.root / "MEMORY.md").read_text(encoding="utf-8")
    assert all(f"[{name}]" in memory_index for name in names)


def test_rule_only_sleep_supersedes_exact_copies_and_retains_their_history(cli):
    names = {"exact-copy-a", "exact-copy-b"}
    for name in sorted(names):
        cli(
            "--agent", "dedup-test", "record", "--type", "fact", "--name", name,
            "--abstract", "Retention requires signed receipts",
            "--body", "Keep the signed receipts for later review.",
            "--field", "project=dedup", "--field", "subject=retention",
            "--valid-from", "2000-01-01",
        )

    report = cli("sleep", "--reason", "none")

    assert [action for action in report["actions"] if action["kind"] == "duplicate-merged"] == [
        {"kind": "duplicate-merged", "target": "exact-copy-b", "detail": "exact-copy-a"}
    ]
    records = {record.name: record for record in Store(cli.root).records(include_invalid=True)}
    assert set(records) == names
    assert all(record.path.is_file() for record in records.values())
    assert records["exact-copy-a"].is_active()
    assert not records["exact-copy-b"].is_active()
    assert records["exact-copy-b"].superseded_by == "exact-copy-a"
    assert {hit["name"] for hit in cli("recall", "retention")["hits"]} == {"exact-copy-a"}
    assert {
        hit["name"] for hit in cli("recall", "retention", "--as-of", "2001-01-01")["hits"]
    } == names
    memory_index = (cli.root / "MEMORY.md").read_text(encoding="utf-8")
    assert "[exact-copy-a]" in memory_index
    assert "[exact-copy-b]" not in memory_index
    assert not any(
        action["kind"] == "duplicate-merged"
        for action in cli("sleep", "--reason", "none")["actions"]
    )


def test_a_plain_sleep_asks_the_library_executor(cli, monkeypatch):
    _near_duplicates(cli)
    proposal = cli("proposals")["proposals"][0]
    reply = json.dumps({"proposal": proposal["id"], "verdict": "reject"})
    monkeypatch.setattr(
        "agent_memory.executor.distiller.distiller", lambda config: lambda prompt: reply
    )
    report = cli("sleep")
    assert [decision["proposal"] for decision in report["decisions"]] == [proposal["id"]]


def test_sleep_can_be_handed_a_reasoner_whose_verdicts_reach_the_store(cli, monkeypatch):
    _near_duplicates(cli)
    proposal = cli("proposals")["proposals"][0]
    reply = json.dumps({"proposal": proposal["id"], "verdict": "reject"})
    monkeypatch.setattr(
        "agent_memory.executor.reasoners.HostReasoner.__call__",
        lambda self, prompt: reply,
    )
    report = cli("sleep", "--reason", "host")
    assert [decision["proposal"] for decision in report["decisions"]] == [proposal["id"]]
    assert proposal["id"] not in {open_one["id"] for open_one in cli("proposals")["proposals"]}


def test_global_flags_are_accepted_after_the_subcommand(tmp_path, capsys):
    root = tmp_path / "store"
    assert main(["init", "--store", str(root)]) == EXIT_OK
    capsys.readouterr()
    assert main([
        "record",
        "--abstract",
        "global flags work after the subcommand",
        "--type",
        "fact",
        "--store",
        str(root),
        "--json",
        "--agent",
        "flag-order",
    ]) == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert Store(root).find(payload["name"]).author == "flag-order"


def test_global_flags_keep_working_before_the_subcommand(tmp_path, capsys):
    root = tmp_path / "store"
    assert main(["--store", str(root), "init"]) == EXIT_OK
    capsys.readouterr()
    assert main(["--store", str(root), "--json", "inspect"]) == EXIT_OK
    assert json.loads(capsys.readouterr().out)["store"] == str(root)


def test_global_flags_work_in_mixed_positions(tmp_path, capsys):
    root = tmp_path / "store"
    assert main(["--store", str(root), "init", "--json"]) == EXIT_OK
    assert json.loads(capsys.readouterr().out)["store"] == str(root)
