import pytest
from agent_memory.core.errors import ValidationError


def test_reversed_interval_cannot_replace_existing_truth(store):
    record = store.record(
        type="fact",
        fields={"subject": "interval"},
        abstract="Interval fixture",
        valid_from="2026-01-05",
    )
    before = record.path.read_bytes()
    record.invalid_at = "2026-01-04"
    with pytest.raises(ValidationError) as raised:
        store.write(record)
    assert "invalid_at" in {error.field for error in raised.value.errors}
    assert record.path.read_bytes() == before
