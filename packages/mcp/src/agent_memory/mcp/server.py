"""MCP over stdio: JSON-RPC framing around the same core calls. No dependency, no algorithm."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Sequence
from typing import TextIO

from agent_memory.core import observation
from agent_memory.core.errors import MemoryStoreError
from agent_memory.core.store import Store

from . import tools

PROTOCOL_VERSION = "2025-06-18"
SERVER_NAME = "agent-memory"
SERVER_VERSION = "0.1.0"
JSONRPC = "2.0"
METHOD_INITIALIZE = "initialize"
METHOD_LIST = "tools/list"
METHOD_CALL = "tools/call"
ERROR_METHOD_NOT_FOUND = -32601
ERROR_INVALID_PARAMS = -32602


Catalogue = Callable[[], list[dict[str, object]]]
Call = Callable[[str, dict[str, object]], dict[str, object]]


def handle(store: Store, request: object) -> dict[str, object] | None:
    return respond(request, tools.catalogue, lambda name, arguments: _call(store, name, arguments))


def respond(request: object, catalogue: Catalogue, call: Call) -> dict[str, object] | None:
    if (
        not isinstance(request, dict)
        or request.get("jsonrpc") != JSONRPC
        or not isinstance(request.get("method"), str)
        or isinstance(request.get("id"), (dict, list, bool))
    ):
        return _error(None, -32600, {"message": "Invalid Request"})
    method = request["method"]
    request_id = request.get("id")
    if "id" not in request:
        return None
    try:
        result = _route(method, request.get("params") or {}, catalogue, call)
    except MemoryStoreError as error:
        return _error(request_id, ERROR_INVALID_PARAMS, error.as_dict())
    except KeyError:
        return _error(request_id, ERROR_METHOD_NOT_FOUND, {"method": method})
    return {"jsonrpc": JSONRPC, "id": request_id, "result": result}


def serve(store: Store, stream_in: TextIO, stream_out: TextIO) -> None:
    serve_lines(stream_in, stream_out, lambda request: handle(store, request))


def serve_lines(
    stream_in: TextIO,
    stream_out: TextIO,
    answer: Callable[[object], dict[str, object] | None],
) -> None:
    for line in stream_in:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            response: dict[str, object] | None = _error(None, -32700, {"message": "Parse error"})
        else:
            response = answer(request)
        if response is None:
            continue
        stream_out.write(json.dumps(response) + "\n")
        stream_out.flush()


def main(argv: Sequence[str] | None = None) -> int:
    store = Store(agent=SERVER_NAME)
    serve(store, sys.stdin, sys.stdout)
    return 0


def _route(method: str, params: object, catalogue: Catalogue, call: Call) -> dict[str, object]:
    arguments = params if isinstance(params, dict) else {}
    if method == METHOD_INITIALIZE:
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        }
    if method == METHOD_LIST:
        return {"tools": catalogue()}
    if method == METHOD_CALL:
        name = str(arguments.get("name") or "")
        payload = arguments.get("arguments")
        return call(name, payload if isinstance(payload, dict) else {})
    raise KeyError(method)


def _call(store: Store, name: str, arguments: dict[str, object]) -> dict[str, object]:
    observation.emit("mcp_tool_call", tool=name, arguments=arguments)
    result = tools.dispatch(store, name, arguments)
    observation.emit("mcp_tool_return", tool=name)
    return {
        "content": [{"type": "text", "text": json.dumps(result, sort_keys=True)}],
        "structuredContent": result,
        "isError": False,
    }


def _error(request_id: object, code: int, data: dict[str, object]) -> dict[str, object]:
    return {
        "jsonrpc": JSONRPC,
        "id": request_id,
        "error": {"code": code, "message": str(data), "data": data},
    }


if __name__ == "__main__":
    raise SystemExit(main())
