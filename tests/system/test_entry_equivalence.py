"""M5 — Invariant 8: the same request through any entry yields the same result."""

import io
import json

from agent_memory.cli.main import EXIT_OK, main
from agent_memory.core.store import Store
from agent_memory.mcp import server, tools

VOLATILE = ("path", "recall_fingerprint")


def _stable(hits):
    return [
        {key: value for key, value in hit.items() if key not in VOLATILE + ("score", "relevance")}
        for hit in hits
    ]


def test_record_through_mcp_is_visible_to_the_cli_and_vice_versa(tmp_path, capsys):
    root = tmp_path / "store"
    store = Store(root, agent="mcp")
    store.init()

    tools.dispatch(
        store,
        tools.TOOL_RECORD,
        {
            "abstract": "Written through MCP about the shared drain window",
            "type": "fact",
            "domain": "project",
            "name": "via-mcp",
        },
    )
    assert main(["--store", str(root), "--json", "record", "--abstract",
                 "Written through the CLI about the shared drain window", "--type", "fact",
                 "--domain", "project", "--name", "via-cli"]) == EXIT_OK
    capsys.readouterr()

    assert main(["--store", str(root), "--json", "recall", "shared drain window"]) == EXIT_OK
    cli_hits = json.loads(capsys.readouterr().out)["hits"]
    mcp_hits = tools.dispatch(
        Store(root, agent="mcp"), tools.TOOL_RECALL, {"query": "shared drain window"}
    )["hits"]

    assert {hit["name"] for hit in cli_hits} == {"via-mcp", "via-cli"}
    assert _stable(cli_hits) == _stable(mcp_hits)


def test_the_two_entries_agree_on_the_recall_fingerprint(tmp_path, capsys):
    root = tmp_path / "store"
    store = Store(root)
    store.init()
    store.record(abstract="Anything at all worth recalling", type="fact", domain="project",
                 name="anything")

    assert main(["--store", str(root), "--json", "recall", "anything"]) == EXIT_OK
    cli = json.loads(capsys.readouterr().out)
    mcp = tools.dispatch(store, tools.TOOL_RECALL, {"query": "anything"})
    assert cli["recall_fingerprint"] == mcp["recall_fingerprint"]


def test_tool_schemas_are_advertised_and_enforced(tmp_path):
    store = Store(tmp_path / "store")
    store.init()
    catalogue = tools.catalogue()
    assert {tool["name"] for tool in catalogue} == set(tools.SCHEMAS)
    assert all(tool["inputSchema"]["type"] == "object" for tool in catalogue)

    response = server.handle(
        store,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tools.TOOL_RECORD, "arguments": {"abstract": "missing fields"}},
        },
    )
    assert response["error"]["data"]["code"] == "validation_error"


def test_unknown_method_and_unknown_tool_both_produce_structured_errors(tmp_path):
    store = Store(tmp_path / "store")
    store.init()
    unknown_method = server.handle(store, {"jsonrpc": "2.0", "id": 1, "method": "nope"})
    assert unknown_method["error"]["code"] == server.ERROR_METHOD_NOT_FOUND

    unknown_tool = server.handle(
        store,
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "memory_nope"}},
    )
    assert unknown_tool["error"]["data"]["code"] == "validation_error"


def test_the_stdio_loop_answers_initialize_and_lists_tools(tmp_path):
    store = Store(tmp_path / "store")
    store.init()
    stream_in = io.StringIO(
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        + "\n"
        + json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        + "\n"
    )
    stream_out = io.StringIO()
    server.serve(store, stream_in, stream_out)
    responses = [json.loads(line) for line in stream_out.getvalue().splitlines()]
    assert responses[0]["result"]["serverInfo"]["name"] == server.SERVER_NAME
    assert len(responses[1]["result"]["tools"]) == len(tools.SCHEMAS)


def test_notifications_get_no_response(tmp_path):
    store = Store(tmp_path / "store")
    store.init()
    assert server.handle(store, {"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
