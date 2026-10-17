"""A rejected as_of surfaces as validation_error; the server lives on for the next call."""

import pytest
from agent_memory.mcp import server


def _call(store, name, arguments):
    request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    return server.handle(store, request)


@pytest.mark.parametrize(
    "as_of",
    ["2026-10-12T23:59:00", "yesterday", "2026-13-01"],
)
def test_bad_as_of_is_rejected_as_validation_error(store, as_of):
    response = _call(store, "memory_recall", {"query": "deploy", "as_of": as_of})
    assert set(response) == {"jsonrpc", "id", "error"}
    error = response["error"]
    assert error["code"] == -32602
    assert error["data"]["code"] == "validation_error"
    assert error["data"]["errors"][0]["field"] == "as_of"


@pytest.mark.parametrize("as_of", ["2026-10-12", "2026-10-12T23:59:00Z"])
def test_good_as_of_recalls_without_error(store, as_of):
    store.record(abstract="Deploys go out on Tuesday", type="decision")
    response = _call(store, "memory_recall", {"query": "deploy", "as_of": as_of})
    assert response["result"]["isError"] is False


def test_server_answers_the_call_after_a_rejected_as_of(store):
    rejected = _call(store, "memory_recall", {"query": "deploy", "as_of": "yesterday"})
    assert "error" in rejected
    assert _call(store, "memory_recall", {"query": "deploy"})["result"]["isError"] is False
