import io
import json

import pytest
from agent_memory.mcp import server


@pytest.mark.parametrize(
    "malformed,code",
    [
        ("{", -32700),
        ("null", -32600),
        ('"text"', -32600),
        ("7", -32600),
        ('{"jsonrpc":"2.0","method":7,"id":1}', -32600),
    ],
)
def test_bad_frame_reports_protocol_error_and_next_request_still_runs(store, malformed, code):
    following = {"jsonrpc": "2.0", "id": 8, "method": "tools/list"}
    output = io.StringIO()
    server.serve(store, io.StringIO(malformed + "\n" + json.dumps(following) + "\n"), output)
    responses = [json.loads(line) for line in output.getvalue().splitlines()]
    assert responses[0]["error"]["code"] == code
    assert responses[0]["id"] is None
    assert responses[1]["id"] == 8
    assert responses[1]["result"]["tools"]


def test_explicit_null_id_receives_a_response(store):
    response = server.handle(store, {"jsonrpc": "2.0", "id": None, "method": "tools/list"})
    assert response is not None
    assert response["id"] is None
    assert response["result"]["tools"]
