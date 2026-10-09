import pytest
from agent_memory.core.errors import ValidationError


@pytest.mark.parametrize("field", ["name", "type"])
def test_identifier_newlines_are_rejected_before_truth_changes(store, field):
    spec = {"abstract": "A useful standing fact", "type": "fact", "name": "memory"}
    spec[field] += "\n"
    before = set(store.layout.truth_files())
    with pytest.raises(ValidationError):
        store.record(**spec)
    assert set(store.layout.truth_files()) == before
