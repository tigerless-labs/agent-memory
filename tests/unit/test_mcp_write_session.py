"""The MCP adapter over the Write toolkit: JSON-RPC framing and nothing of its own."""

import io
import json

from agent_memory.core import reconcile, sessions, toolkit
from agent_memory.mcp import server, write_session


def _batch(store, tmp_path):
    store.config.write.recall_with_evidence_enabled = True
    store.config.save(store.root)
    old = store.record(
        type="fact",
        fields={"project": "pipeline", "subject": "queue timeout"},
        abstract="Queue timeout is 20 seconds",
        body="Set in infra/queue.yaml.",
    )
    pointer = store.archive.append_session("boundary", ["user: the queue timeout is 30 seconds"])
    messages = sessions.resolve(store.layout, pointer)
    sheet = reconcile.build(store, "boundary", messages)
    empty = reconcile.Sheet(
        sheet.session, sheet.pointer, (), sheet.menus, sheet.profile, sheet.slots, sheet.messages
    )
    kit = toolkit.WriteToolkit(store, empty)
    directory = tmp_path / "batch"
    directory.mkdir()
    kit.save_seed(directory)
    return kit, directory, old


def _rpc(request_id, method, params=None):
    message = {"jsonrpc": "2.0", "method": method}
    if request_id is not None:
        message["id"] = request_id
    if params is not None:
        message["params"] = params
    return json.dumps(message)


def _call(request_id, name, arguments):
    return _rpc(request_id, "tools/call", {"name": name, "arguments": arguments})


def _serve(directory, *lines):
    stream_out = io.StringIO()
    write_session.serve(directory, io.StringIO("\n".join(lines) + "\n"), stream_out)
    return [json.loads(line) for line in stream_out.getvalue().splitlines()]


def _supersede(handle):
    return {
        "type": "fact",
        "op": "supersede",
        "handle": handle,
        "fields": {"project": "pipeline", "subject": "queue timeout 30s"},
        "abstract": "Queue timeout is 30 seconds",
    }


def test_the_adapter_lists_exactly_the_toolkit_catalogue(store, tmp_path):
    kit, directory, _ = _batch(store, tmp_path)
    initialize, listing = _serve(directory, _rpc(1, "initialize"), _rpc(2, "tools/list"))
    assert initialize["result"]["capabilities"] == {"tools": {}}
    offered = {tool["name"]: tool for tool in listing["result"]["tools"]}
    assert set(offered) == {spec.name for spec in kit.catalogue()}
    for spec in kit.catalogue():
        assert offered[spec.name]["inputSchema"] == spec.schema
        assert offered[spec.name]["description"] == spec.description


def test_tool_calls_run_the_toolkit_and_the_record_flows_back(store, tmp_path):
    kit, directory, old = _batch(store, tmp_path)
    looked, submitted = _serve(
        directory,
        _call(1, toolkit.TOOL_RECALL, {toolkit.ARG_QUERY: "queue timeout"}),
        _call(2, toolkit.TOOL_SUBMIT, {toolkit.ARG_OPERATIONS: [_supersede(old.name)]}),
    )
    assert looked["result"]["isError"] is False
    assert old.name in looked["result"]["content"][0]["text"]
    assert submitted["result"]["isError"] is False
    kit.absorb_directory(directory)
    assert kit.submission == [_supersede(old.name)]
    assert reconcile.check(kit.submission[0], kit.sheet) == []


def test_bounded_evidence_and_its_authorized_handle_flow_across_mcp(store, tmp_path):
    kit, directory, old = _batch(store, tmp_path)
    looked, submitted = _serve(
        directory,
        _call(
            1,
            toolkit.TOOL_RECALL_WITH_EVIDENCE,
            {toolkit.ARG_QUERY: "queue timeout"},
        ),
        _call(2, toolkit.TOOL_SUBMIT, {toolkit.ARG_OPERATIONS: [_supersede(old.name)]}),
    )

    evidence = looked["result"]["content"][0]["text"]
    assert looked["result"]["isError"] is False
    assert old.name in evidence and "infra/queue.yaml" in evidence
    assert submitted["result"]["isError"] is False
    kit.absorb_directory(directory)
    assert old.name in kit.sheet.handle_names()
    assert kit.submission == [_supersede(old.name)]


def test_a_refused_tool_call_is_a_tool_error_not_a_protocol_error(store, tmp_path):
    kit, directory, old = _batch(store, tmp_path)
    (refused,) = _serve(
        directory, _call(1, toolkit.TOOL_SUBMIT, {toolkit.ARG_OPERATIONS: [_supersede(old.name)]})
    )
    assert "error" not in refused
    assert refused["result"]["isError"] is True
    kit.absorb_directory(directory)
    assert kit.submission is None


def test_unknown_methods_are_protocol_errors_and_notifications_get_no_reply(store, tmp_path):
    _, directory, _ = _batch(store, tmp_path)
    replies = _serve(directory, _rpc(None, "notifications/initialized"), _rpc(7, "resources/list"))
    assert len(replies) == 1
    assert replies[0]["id"] == 7
    assert replies[0]["error"]["code"] == server.ERROR_METHOD_NOT_FOUND


def test_main_serves_the_batch_named_on_its_command_line(store, tmp_path, monkeypatch):
    kit, directory, old = _batch(store, tmp_path)
    stream_out = io.StringIO()
    monkeypatch.setattr(
        "sys.stdin", io.StringIO(_call(1, toolkit.TOOL_READ, {toolkit.ARG_NAME: old.name}) + "\n")
    )
    monkeypatch.setattr("sys.stdout", stream_out)
    assert write_session.main([str(directory)]) == 0
    (reply,) = [json.loads(line) for line in stream_out.getvalue().splitlines()]
    assert "infra/queue.yaml" in reply["result"]["content"][0]["text"]
    kit.absorb_directory(directory)
    assert old.name in kit.sheet.handle_names()


def test_the_public_server_keeps_its_own_catalogue(store):
    reply = server.handle(store, json.loads(_rpc(1, "tools/list")))
    names = {tool["name"] for tool in reply["result"]["tools"]}
    assert toolkit.TOOL_SUBMIT not in names
