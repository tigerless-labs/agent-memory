import pytest
from agent_memory.cli.main import main
from agent_memory.core.errors import NotFoundError, ValidationError
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
    assert main(["--store", str(store.root), "correct", first["name"], "--clear-links"]) == 0
    assert store.find(first["name"]).links == []
    dispatch(store, "memory_correct", {"name": first["name"], "links": ["quasar-new"]})
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


@pytest.mark.parametrize("adapter", ["cli", "mcp"])
@pytest.mark.parametrize(
    ("source", "links", "error"),
    [
        ("missing", ["target"], NotFoundError),
        ("inactive-source", ["target"], ValidationError),
        ("source", ["missing"], ValidationError),
        ("source", ["inactive-target"], ValidationError),
        ("source", ["source"], ValidationError),
        ("source", ["target", "target"], ValidationError),
    ],
)
def test_cli_and_mcp_reject_same_invalid_corrections(store, capsys, adapter, source, links, error):
    for name in ("source", "target", "inactive-source", "inactive-target"):
        store.record(type="fact", name=name, abstract=f"Memory {name}")
    store.delete("inactive-source")
    store.delete("inactive-target")
    before = {record.name: record.path.read_bytes() for record in store.records(True)}
    if adapter == "cli":
        args = ["--store", str(store.root), "correct", source]
        for target in links:
            args.extend(["--link", target])
        assert main(args) == (1 if error is NotFoundError else 2)
        capsys.readouterr()
    else:
        with pytest.raises(error):
            dispatch(store, "memory_correct", {"name": source, "links": links})
    assert {record.name: record.path.read_bytes() for record in store.records(True)} == before


@pytest.mark.parametrize("adapter", ["cli", "mcp"])
def test_cli_and_mcp_preserve_legacy_links_only_when_omitted(store, capsys, adapter):
    store.record(type="fact", name="target", abstract="Target")
    store.record(type="fact", name="source", abstract="Old abstract", links=["target"])
    store.delete("target")
    if adapter == "cli":
        assert main(["--store", str(store.root), "correct", "source", "--abstract", "New"]) == 0
        assert main(["--store", str(store.root), "correct", "source", "--link", "target"]) == 2
        capsys.readouterr()
    else:
        dispatch(store, "memory_correct", {"name": "source", "abstract": "New"})
        with pytest.raises(ValidationError):
            dispatch(store, "memory_correct", {"name": "source", "links": ["target"]})
    assert store.find("source").abstract == "New"
    assert store.find("source").links == ["target"]


@pytest.mark.parametrize("adapter", ["cli", "mcp"])
def test_cli_and_mcp_correct_text_and_replace_valid_links(store, adapter):
    for name in ("source", "old-target", "new-target"):
        store.record(type="fact", name=name, abstract=f"Old {name}", body=f"Old {name} body")
    store.correct("source", links=["old-target"])
    if adapter == "cli":
        assert (
            main(
                [
                    "--store", str(store.root), "correct", "source", "--abstract", "New abstract",
                    "--body", "New body", "--link", "new-target",
                ]
            )
            == 0
        )
    else:
        dispatch(
            store,
            "memory_correct",
            {
                "name": "source", "abstract": "New abstract", "body": "New body",
                "links": ["new-target"],
            },
        )
    source = store.find("source")
    assert (source.abstract, source.body, source.links) == (
        "New abstract", "New body", ["new-target"]
    )
