import pytest
from agent_memory.cli.main import main
from agent_memory.core.errors import ValidationError
from agent_memory.mcp.tools import dispatch


def test_cli_and_mcp_share_relationship_boundaries(store, capsys):
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
    assert main(["--store", str(store.root), "correct", first["name"], "--link", "quasar-new"]) == 0
    assert store.find(first["name"]).links == ["quasar-new"]
    dispatch(store, "memory_correct", {"name": first["name"], "links": []})
    assert store.find(first["name"]).links == []
    assert store.read("quasar-new").text == "New fact"
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
