"""MCP over stdio: JSON-RPC framing around the same core calls. No dependency, no algorithm."""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from typing import TextIO

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


def handle(store: Store, request: dict[str, object]) -> dict[str, object] | None:
    method = str(request.get("method") or "")
    request_id = request.get("id")
    if request_id is None:
        return None
    try:
        result = _route(store, method, request.get("params") or {})
    except MemoryStoreError as error:
        return _error(request_id, ERROR_INVALID_PARAMS, error.as_dict())
    except KeyError:
        return _error(request_id, ERROR_METHOD_NOT_FOUND, {"method": method})
    return {"jsonrpc": JSONRPC, "id": request_id, "result": result}


def serve(store: Store, stream_in: TextIO, stream_out: TextIO) -> None:
    for line in stream_in:
        if not line.strip():
            continue
        response = handle(store, json.loads(line))
        if response is None:
            continue
        stream_out.write(json.dumps(response) + "\n")
        stream_out.flush()


def main(argv: Sequence[str] | None = None) -> int:
    store = Store(agent=SERVER_NAME)
    serve(store, sys.stdin, sys.stdout)
    return 0


def _route(store: Store, method: str, params: object) -> dict[str, object]:
    arguments = params if isinstance(params, dict) else {}
    if method == METHOD_INITIALIZE:
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        }
    if method == METHOD_LIST:
        return {"tools": tools.catalogue()}
    if method == METHOD_CALL:
        name = str(arguments.get("name") or "")
        payload = arguments.get("arguments")
        result = tools.dispatch(store, name, payload if isinstance(payload, dict) else {})
        return {
            "content": [{"type": "text", "text": json.dumps(result, sort_keys=True)}],
            "structuredContent": result,
            "isError": False,
        }
    raise KeyError(method)


def _error(request_id: object, code: int, data: dict[str, object]) -> dict[str, object]:
    return {
        "jsonrpc": JSONRPC,
        "id": request_id,
        "error": {"code": code, "message": str(data), "data": data},
    }


if __name__ == "__main__":
    raise SystemExit(main())
