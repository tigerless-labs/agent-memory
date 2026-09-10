import pytest
from agent_memory.cli.main import main
from agent_memory.core.errors import NotFoundError
from agent_memory.mcp.tools import dispatch


def test_cli_and_mcp_share_archive_boundaries(store, capsys):
    first = dispatch(
        store,
        "memory_record",
        {"type": "fact", "name": "quasar-old", "abstract": "Quasar old", "body": "Old evidence"},
    )
    dispatch(
        store,
        "memory_record",
        {"type": "fact", "name": "quasar-new", "abstract": "Quasar new", "body": "New fact"},
    )
    dispatch(store, "memory_correct", {"name": first["name"], "supersede_with": "quasar-new"})
    with pytest.raises(NotFoundError):
        dispatch(store, "memory_read", {"name": first["name"]})
    assert (
        dispatch(store, "memory_read", {"name": first["name"], "include_invalid": True})["text"]
        == "Old evidence"
    )
    assert main(["--store", str(store.root), "read", first["name"], "--history"]) == 0
    assert "Old evidence" in capsys.readouterr().out


def test_cli_invalidation_retains_history_and_excludes_normal_reads(store, capsys):
    prefix = ["--store", str(store.root)]
    assert (
        main(
            prefix
            + [
                "record",
                "--type",
                "fact",
                "--name",
                "quasar-cli",
                "--abstract",
                "Quasar fact",
                "--body",
                "Original evidence",
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert main(prefix + ["read", "quasar-cli"]) == 0
    assert "Original evidence" in capsys.readouterr().out
    assert main(prefix + ["recall", "Quasar"]) == 0
    assert "quasar-cli" in capsys.readouterr().out
    for _ in range(2):
        assert main(prefix + ["delete", "quasar-cli"]) == 0
        capsys.readouterr()
    assert store.find("quasar-cli").path.is_relative_to(store.layout.archived_memories)
    assert main(prefix + ["read", "quasar-cli"]) != 0
    capsys.readouterr()
    for command in ("recall", "context"):
        assert main(prefix + [command, "Quasar"]) == 0
        assert "quasar-cli" not in capsys.readouterr().out
    assert main(prefix + ["read", "quasar-cli", "--history"]) == 0
    assert "Original evidence" in capsys.readouterr().out
