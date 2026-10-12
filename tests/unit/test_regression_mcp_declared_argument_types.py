import pytest
from agent_memory.core.errors import ValidationError
from agent_memory.mcp.tools import dispatch


@pytest.mark.parametrize(
    "tool,args",
    [
        ("memory_recall", {"query": {"unexpected": "object"}}),
        ("memory_recall", {"query": None}),
        ("memory_recall", {"query": "fixture", "limit": "2"}),
        ("memory_recall", {"query": "fixture", "limit": True}),
        ("memory_recall", {"query": "fixture", "limit": 0}),
        ("memory_recall", {"query": "fixture", "limit": -1}),
        ("memory_record", {"abstract": "Fixture", "type": "decision", "body": {"lost": "body"}}),
        ("memory_record", {"abstract": "Fixture", "type": "decision", "create_group": "false"}),
        ("memory_record", {"abstract": "Fixture", "type": "decision", "fields": {"key": 7}}),
    ],
)
def test_invalid_declared_types_do_not_reach_truth(store, tool, args):
    before = {str(p): p.read_bytes() for p in store.layout.truth_files()}
    with pytest.raises(ValidationError):
        dispatch(store, tool, args)
    assert {str(p): p.read_bytes() for p in store.layout.truth_files()} == before


@pytest.mark.parametrize(
    "tool,args",
    [
        ("memory_record", {"abstract": "Fixture", "type": "decision", "links": [123]}),
        ("memory_record", {"abstract": "Fixture", "type": "decision", "provenance": [123]}),
        ("memory_merge", {"names": [123], "abstract": "Fixture", "body": "Fixture"}),
    ],
)
def test_array_items_follow_declared_string_schema(store, tool, args):
    with pytest.raises(ValidationError):
        dispatch(store, tool, args)
