import pytest
from agent_memory.core.errors import ValidationError


def memory(store, name="old-memory", **kwargs):
    return store.record(
        type="fact", name=name, abstract="Quasar queue timeout", body="Old fact", **kwargs
    )


@pytest.mark.parametrize("links", [["missing"], ["source"]])
def test_invalid_relationship_additions_are_rejected(store, links):
    memory(store, "source")
    with pytest.raises(ValidationError):
        store.correct("source", links=links)
    assert store.find("source").links == []


def test_relationship_replacement_and_invalid_endpoints(store):
    memory(store, "source")
    memory(store, "target")
    assert store.correct("source", links=["target"]).links == ["target"]
    assert store.correct("source", links=[]).links == []
    store.delete("target")
    with pytest.raises(ValidationError):
        store.correct("source", links=["target"])
    with pytest.raises(ValidationError):
        store.correct("source", supersede_with="target")
    with pytest.raises(ValidationError):
        store.correct("target", body="resurrection")


def test_existing_historical_links_survive_other_metadata_updates(store):
    target = memory(store, "target")
    source = memory(store, "source", links=[target.name])
    store.delete(target.name)
    updated = store.correct(source.name, abstract="Updated quasar wording")
    assert updated.links == [target.name]
    assert store.correct(source.name, links=[]).links == []


def test_unlink_does_not_delete_target_or_evidence(store):
    target = memory(store, "target", provenance=["original evidence"])
    source = memory(store, "source", links=[target.name])
    before = target.path.read_bytes()
    store.correct(source.name, links=[])
    assert store.read(target.name).text == target.body
    assert target.path.read_bytes() == before
    assert store.archive.provenance_of(target.name)


@pytest.mark.parametrize("operation", ["record", "correct", "write"])
@pytest.mark.parametrize("target", ["missing", "source", "inactive"])
def test_all_link_write_paths_validate_before_persisting(store, operation, target):
    memory(store, "source")
    memory(store, "inactive")
    store.delete("inactive")
    before = store.find("source").path.read_bytes()
    with pytest.raises(ValidationError):
        if operation == "record":
            memory(store, "source", links=[target])
        elif operation == "correct":
            store.correct("source", links=[target])
        else:
            candidate = store.find("source")
            candidate.links = [target]
            store.write(candidate)
    assert store.find("source").path.read_bytes() == before


def test_missing_successor_does_not_change_source(store):
    from agent_memory.core.errors import NotFoundError

    source = memory(store, "source")
    before = source.path.read_bytes()
    with pytest.raises(NotFoundError):
        store.correct(source.name, supersede_with="missing")
    assert source.path.read_bytes() == before
