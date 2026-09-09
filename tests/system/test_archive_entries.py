import pytest
from agent_memory.cli.main import main
from agent_memory.core.errors import NotFoundError, ValidationError
from agent_memory.mcp.tools import dispatch


def test_cli_and_mcp_share_archive_and_relationship_boundaries(store, capsys):
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
    dispatch(store, "memory_correct", {"name": first["name"], "links": ["quasar-new"]})
    assert store.find(first["name"]).links == ["quasar-new"]
    with pytest.raises(ValidationError):
        dispatch(
            store, "memory_record", {"type": "fact", "abstract": "Bad link", "links": ["missing"]}
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
    for tool in ("memory_gc", "memory_delete", "memory_unlink"):
        with pytest.raises(ValidationError):
            dispatch(store, tool, {"name": first["name"]})


@pytest.mark.parametrize("links", ["target", None, [None], {}])
def test_malformed_relationship_input_cannot_clear_links(store, links):
    store.record(type="fact", name="target", abstract="Target memory")
    store.record(type="fact", name="source", abstract="Source memory", links=["target"])
    with pytest.raises(ValidationError):
        dispatch(store, "memory_correct", {"name": "source", "links": links})
    assert store.find("source").links == ["target"]
